# mysql-ibmcloud-vpc-snapshot.py

Python script that will create IBM Cloud VPC block volume snapshots while coordinating with MySQL and the underlying OS filesystem to insure database integrity.  NOTE:  this script has been tested with Python 3.8 and Python 3.9.

Procedures this script follows:
* validate the BLOCK_VOLUME_ID exists
* stop the mysql replica slave thread (if STOP_REPLICA is true)
* flush all mysql tables and close them with a lock to prevent further writes
* create the VPC Block Volume Snapshot
* query the snapshot every two seconds until the "captured_at" attribute is set
* unlock the MySQL tables
* start the mysql replica slave thread (if STOP_REPLICA is true) 

Below are the environment variables (can also be added to a local .env file) that are used to customize runtime of this script:
* IBMCLOUD_API_KEY - the IBM Cloud API key used to create the snapshot.  Required.
* MYSQL_HOST - the MySQL host to connect to. Defaults to localhost.
* MYSQL_PWD - the MySQL password to use.  Required.
* MYSQL_USER - the MySQL user to use.  Defaults to the USER env variable.
* LOG_LEVEL - the Python logging module level.  Defaults to INFO
* BLOCK_VOLUME_ID - the IBM Cloud VPC Block Volume ID for which the snapshot will be created.  Required
* SNAP_NAME - the name prefix for the snapshot.  Defaults to "my-snap".
* STOP_REPLICA - boolean to run "STOP SLAVE" before locking tables.  Defaults to false.

Snapshots are created by prepending the SNAP_NAME and then followed by a "-" and then the current year, month, day, hour, and minute.

The script will exit if any of the required environment variables are not supplied or if the BLOCK_VOLUME_ID cannot be found.

It's suggested that a Python virtual environment be setup to run this script and install the required Python modules. Here are some procedures to run to install and run:

* git clone git@github.com:rsumner/mysql-ibmcloud-vpc-snapshot.git
* python3 -m venv mysql-ibmcloud-vpc-snapshot
* source mysql-ibmcloud-vpc-snapshot/bin/activate
* pip install -r mysql-ibmcloud-vpc-snapshot/requirements.txt
* create a mysql-ibmcloud-vpc-snapshot/.env file with all variable names mentioned above
  * obtain the BLOCK_VOLUME_ID that you want to create snapshots for from the IBM Cloud portal, CLI, or API 
