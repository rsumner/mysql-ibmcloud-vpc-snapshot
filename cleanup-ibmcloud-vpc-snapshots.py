import os
import sys
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from ibm_vpc import VpcV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_cloud_sdk_core import ApiException
from collections import OrderedDict

load_dotenv()
IBMCLOUD_API_KEY = os.getenv('IBMCLOUD_API_KEY') or sys.exit('IBMCLOUD_API_KEY env variable is required')
LOG_LEVEL = os.getenv('LOG_LEVEL', default='INFO')
BLOCK_VOLUME_ID = os.getenv('BLOCK_VOLUME_ID') or sys.exit('BLOCK_VOLUME_ID env variable is required')
SNAP_NAME = os.getenv('SNAP_NAME', default='my-snap')
INC_DAYS=7
DAILY_DAYS=30
USE_FAKE_DATA=False

FAKE_DATA = [
    {'id': 'asdf-asdf-1', 'name': 'snap-1', 'created_at': '2022-11-25T20:35:13Z', 'lifecycle_state': 'stable', 'deletable': True},
    {'id': 'asdf-asdf-2', 'name': 'snap-2', 'created_at': '2022-12-25T00:35:13Z', 'lifecycle_state': 'stable', 'deletable': True},
    {'id': 'asdf-asdf-3', 'name': 'snap-3', 'created_at': '2022-12-25T06:35:13Z', 'lifecycle_state': 'stable', 'deletable': True},
    {'id': 'asdf-asdf-3a', 'name': 'snap-3a', 'created_at': '2022-12-25T12:35:13Z', 'lifecycle_state': 'stable', 'deletable': True},
    {'id': 'asdf-asdf-3b', 'name': 'snap-3b', 'created_at': '2022-12-25T00:10:13Z', 'lifecycle_state': 'stable', 'deletable': True},    
    {'id': 'asdf-asdf-4', 'name': 'snap-4', 'created_at': '2022-12-26T20:35:13Z', 'lifecycle_state': 'stable', 'deletable': True},
    {'id': 'asdf-asdf-5', 'name': 'snap-5', 'created_at': '2022-12-27T20:35:13Z', 'lifecycle_state': 'stable', 'deletable': True},
    {'id': 'asdf-asdf-6', 'name': 'snap-6', 'created_at': '2022-12-28T20:35:13Z', 'lifecycle_state': 'stable', 'deletable': True},
    {'id': 'asdf-asdf-7', 'name': 'snap-7', 'created_at': '2022-12-29T20:35:13Z', 'lifecycle_state': 'stable', 'deletable': True},
    {'id': 'asdf-asdf-8', 'name': 'snap-8', 'created_at': '2022-12-29T20:35:13Z', 'lifecycle_state': 'stable', 'deletable': True},
    {'id': 'asdf-asdf-9', 'name': 'snap-9', 'created_at': '2022-12-30T20:35:13Z', 'lifecycle_state': 'stable', 'deletable': True},
    {'id': 'asdf-asdf-10', 'name': 'snap-10', 'created_at': '2023-01-01T20:35:13Z', 'lifecycle_state': 'stable', 'deletable': True},
    {'id': 'asdf-asdf-11', 'name': 'snap-11', 'created_at': '2023-01-01T20:35:13Z', 'lifecycle_state': 'stable', 'deletable': True},
    {'id': 'asdf-asdf-12', 'name': 'snap-12', 'created_at': '2023-01-02T20:35:13Z', 'lifecycle_state': 'stable', 'deletable': True},
    {'id': 'asdf-asdf-13', 'name': 'snap-13', 'created_at': '2023-01-03T20:35:13Z', 'lifecycle_state': 'stable', 'deletable': True}
]

logging.basicConfig(level=getattr(logging, LOG_LEVEL), format='%(asctime)s %(levelname)s: %(message)s')

ibm_iam = IAMAuthenticator(IBMCLOUD_API_KEY)
ibm_service = VpcV1(authenticator=ibm_iam)

to_delete=[]
days = dict()

try:
    if USE_FAKE_DATA:
        snapshots = FAKE_DATA
    else:
        snapshots = ibm_service.list_snapshots(source_volume_id=BLOCK_VOLUME_ID).get_result()['snapshots']
    for snapshot in snapshots:
        if snapshot['lifecycle_state'] == 'stable' and snapshot['deletable']:
            logging.debug("Found stable and deletable snapshot {snapshot[name]} id:{snapshot[id]} created at {snapshot[created_at]}".format(snapshot=snapshot))
            snap_datetime = datetime.fromisoformat(snapshot['created_at'].replace('Z', '+00:00'))
            snap_delta_days = (datetime.now(timezone.utc) - snap_datetime).days
            #logging.debug("Snapshot is {days} days old".format(days=snap_delta_days))

            # first, get rid of anything older than the DAILY_DAYS
            if(snap_delta_days > DAILY_DAYS):
                logging.debug("Marking snapshot {id} to delete because it is older than {days} days".format(id=snapshot['id'], days=DAILY_DAYS))
                to_delete.append(snapshot['id'])     
            elif(snap_delta_days > INC_DAYS):
                # we want the oldest snapshot for any given day
                if(snap_delta_days in days):
                    stored_snap_datetime = datetime.fromisoformat(days[snap_delta_days]['created_at'].replace('Z', '+00:00'))
                    if(snap_datetime < stored_snap_datetime):
                        # add the old one to the delete list
                        logging.debug(
                            "Marking snapshot {oldid} to delete because it is older than {days} days but newer than {id}".format(
                                oldid=days[snap_delta_days]['id'], days=INC_DAYS, id=snapshot['id']
                            )
                        )
                        to_delete.append(days[snap_delta_days]['id'])
                        # replace it with the new one
                        days[snap_delta_days] = snapshot
                    else:
                        # it's newer, so just delete this one
                        logging.debug(
                            "Marking snapshot {id} to delete because it is older than {days} days but newer than {oldid}".format(
                                id=snapshot['id'], oldid=days[snap_delta_days]['id'], days=INC_DAYS
                            )
                        )
                        to_delete.append(snapshot['id'])
                else:
                    # we always keep one per day between INC_DAYS and DAILY_DAYS.  we will purge the others as we go
                    days[snap_delta_days] = snapshot
            else:
                # and we keep everything that is less than INC_DAYS
                logging.debug("Keeping snapshot {id} because it is only {days} days old".format(id=snapshot['id'], days=snap_delta_days))
        else:
            logging.warn("Found snapshot {name} id:{id} that is not stable and deletable".format(name=snapshot['name'], id=snapshot['id']))
except ApiException as e:
    logging.error("API call to get snapshots failed " + str(e.code) + ": " + e.message)

for id in to_delete:
    try:
        logging.info("Deleting snapshot {id}".format(id=id))
        ibm_service.delete_snapshot(id=id)
    except ApiException as e:
        logging.error("API call to delete snapshot failed " + str(e.code) + ": " + e.message)
