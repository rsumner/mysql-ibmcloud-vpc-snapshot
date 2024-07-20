import os
import subprocess
import sys
import logging
import mysql.connector
import time
from time import sleep
from datetime import datetime
from dotenv import load_dotenv
from ibm_vpc import VpcV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_cloud_sdk_core import ApiException

load_dotenv()
IBMCLOUD_API_KEY = os.getenv('IBMCLOUD_API_KEY') or sys.exit('IBMCLOUD_API_KEY env variable is required')
MYSQL_HOST = os.getenv('MYSQL_HOST', default='localhost') 
MYSQL_PWD = os.getenv('MYSQL_PWD') or sys.exit('MYSQL_PWD env variable is required')
MYSQL_USER = os.getenv('MYSQL_USER', default=os.getenv('USER'))
LOG_LEVEL = os.getenv('LOG_LEVEL', default='INFO')
BLOCK_VOLUME_ID = os.getenv('BLOCK_VOLUME_ID') or sys.exit('BLOCK_VOLUME_ID env variable is required')
MOUNT_POINT = os.getenv('MOUNT_POINT') or sys.exit('MOUNT_POINT env variable is required')
SNAP_NAME = os.getenv('SNAP_NAME', default='my-snap')
STOP_REPLICA = os.getenv('STOP_REPLICA', default='False') == 'True'
FREEZE_FS = os.getenv('FREEZE_FS', default='False') == 'True'
SNAPSHOT_TIMEOUT = os.getenv('SNAPSHOT_TIMEOUT', default=300)

#logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logging.getLogger().setLevel(getattr(logging, LOG_LEVEL))
logging.getLogger().handlers[0].setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))

ibm_iam = IAMAuthenticator(IBMCLOUD_API_KEY)
ibm_service = VpcV1(authenticator=ibm_iam)

# first, make sure we have a valid block volume before doing anything
try:
    block_volume = ibm_service.get_volume(id=BLOCK_VOLUME_ID).get_result()
    logging.debug(block_volume)
except ApiException as e:
    sys.exit("API call to get block volume failed " + str(e.code) + ": " + e.message)

if FREEZE_FS is True:
    # connect to mysql and lock/close the tables
    mysql_connection = mysql.connector.connect(user=MYSQL_USER, password=MYSQL_PWD,
                                               host=MYSQL_HOST, database='mysql')
    mysql_cursor = mysql_connection.cursor()

    if STOP_REPLICA is True:
        mysql_cursor.execute('STOP SLAVE')
        mysql_cursor.execute('SHOW SLAVE STATUS')
        slave_status = dict(zip(mysql_cursor.column_names, mysql_cursor.fetchone()))
        logging.info("Stopped MySQL slave thread. Dumping current slave status")
        logging.info(slave_status)

    logging.info("Flushing MySQL tables with READ LOCK")
    mysql_cursor.execute('FLUSH TABLES WITH READ LOCK')
    os.sync()
    os.sync()
    os.sync()
    logging.info("Freezing XFS filesystem")
    subprocess.run(["/usr/sbin/xfs_freeze", "-f", MOUNT_POINT])

snapshot_created = False
try:
    snap_prototype = {}
    snap_prototype['name'] = SNAP_NAME
    snap_prototype['source_volume'] = {}
    snap_prototype['source_volume']['id'] = BLOCK_VOLUME_ID
    snapshot = ibm_service.create_snapshot(snapshot_prototype={
        'name': SNAP_NAME + '-' + datetime.now().strftime('%Y%m%d%H%M'),
        'source_volume': {'id': BLOCK_VOLUME_ID}
    }).get_result()
    logging.debug(snapshot)
    logging.info('Created snapshot id ' + snapshot['id'])
    snapshot_created = True
except ApiException as e:
    logging.error("API call to create snapshot failed" +  str(e.code) + ": " + e.message)

# query snapshot until we see captured_at defined in the snapshot or we timeout first
snapshot_captured = False
if snapshot_created:
    timeout = time.time() + SNAPSHOT_TIMEOUT
    while True:
        try:
            poll_snap = ibm_service.get_snapshot(id=snapshot['id']).get_result()
            logging.debug(poll_snap)
            if('captured_at' in poll_snap and poll_snap['captured_at']):
                logging.info('Snapshot captured_at ' + poll_snap['captured_at'])
                snapshot_captured = True
                break
            if time.time() > timeout:
                break
            sleep(2)
        except ApiException as e:
            logging.error("API call to get snapshot failed " + str(e.code) + ": " + e.message)
            break

if FREEZE_FS:
    logging.info("Unfreezing XFS filesystem")
    subprocess.run(["/usr/sbin/xfs_freeze", "-u", MOUNT_POINT])
    logging.info("Unlocking MySQL tables")
    mysql_cursor.execute('UNLOCK TABLES')

    if STOP_REPLICA:
        logging.info("Starting MySQL slave thread")
        mysql_cursor.execute('START SLAVE')

    mysql_cursor.close()
    mysql_connection.close()

