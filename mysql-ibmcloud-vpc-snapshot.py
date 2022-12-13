import os
import sys
import logging
import mysql.connector
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
SNAP_NAME = os.getenv('SNAP_NAME', default='my-snap')
STOP_REPLICA = os.getenv('STOP_REPLICA', default=False)

logging.basicConfig(level=getattr(logging, LOG_LEVEL))

ibm_iam = IAMAuthenticator(IBMCLOUD_API_KEY)
ibm_service = VpcV1(authenticator=ibm_iam)

# first, make sure we have a valid block volume before doing anything
try:
    block_volume = ibm_service.get_volume(id=BLOCK_VOLUME_ID).get_result()
    logging.debug(block_volume)
    logging.info("Confirmed block volume exist")
except ApiException as e:
  sys.exit("API call to get block volume failed " + str(e.code) + ": " + e.message)

# connect to mysql and lock/close the tables
mysql_connection = mysql.connector.connect(user=MYSQL_USER, password=MYSQL_PWD,
                              host=MYSQL_HOST, database='mysql')
mysql_cursor = mysql_connection.cursor()
if(STOP_REPLICA):
    mysql_cursor.execute('STOP SLAVE')
    logging.info("Stopped MySQL replica slave thread")
mysql_cursor.execute('FLUSH TABLES WITH READ LOCK')
logging.info("Flushed MySQL tables and created read lock")
os.sync()
os.sync()
os.sync()
logging.info("Flushed OS filesystem IOPS")

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
    logging.info('Created VPC Block Volume snapshot id ' + snapshot['id'])
except ApiException as e:
    logging.error("API call to create snapshot failed" +  str(e.code) + ": " + e.message)

# query snapshot until we have a captured_at
while True:
    try:
        poll_snap = ibm_service.get_snapshot(id=snapshot['id']).get_result()
        logging.debug(poll_snap)
        if('captured_at' in poll_snap and poll_snap['captured_at']):
            logging.info('VPC Block Volume snapshot captured_at ' + poll_snap['captured_at'])
            break
        sleep(2)
    except ApiException as e:
        logging.error("API call to get snapshot failed " + str(e.code) + ": " + e.message)
        break

mysql_cursor.execute('UNLOCK TABLES')
logging.info("Unlocked MySQL tables")
if(STOP_REPLICA):
    mysql_cursor.execute('START SLAVE')
    logging.info("Started MySQL replica slave thread")
mysql_cursor.close()
mysql_connection.close()