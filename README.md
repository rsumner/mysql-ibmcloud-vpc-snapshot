Python script that will create IBM Cloud VPC block volume snapshots while coordinating with MySQL and the underlying OS filesystem to insure database integrity.

Environment variables (can also be added to a local .env file):
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