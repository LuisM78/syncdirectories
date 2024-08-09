import os
import paramiko
import schedule
import time
import logging
from stat import S_ISDIR

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Read environment variables
remote_host = os.getenv('SERVER_IP', '192.168.0.110')
username = os.getenv('SSH_USERNAME', 'luism')
key_file = os.getenv('SSH_KEY_FILE', 'C:\\Users\\luism\\.ssh\\id_rsa')
project_dir = 'C:\\Users\\luism\\Documents\\my_python_project'

# Configuration
local_dir = 'C:\\Users\\luism\\Documents\\sync_folder'
remote_dir = 'C:\\Users\\luism\\OneDrive\\Desktop\\tosync'
remote_port = 22

def ssh_connect():
    """Establish SSH connection using Paramiko."""
    logging.info('Establishing SSH connection...')
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(remote_host, port=remote_port, username=username, key_filename=key_file)
        logging.info('SSH connection established.')
    except Exception as e:
        logging.error(f'Error establishing SSH connection: {e}')
        raise
    return ssh

def sftp_connect(ssh):
    """Establish SFTP connection using Paramiko."""
    logging.info('Establishing SFTP connection...')
    return ssh.open_sftp()

def sync_files(sftp, local_path, remote_path):
    """Synchronize files from local to remote directory."""
    logging.info('Starting file synchronization (local to remote)...')
    for root, dirs, files in os.walk(local_path):
        for dirname in dirs:
            local_dir_path = os.path.join(root, dirname)
            remote_dir_path = os.path.join(remote_path, os.path.relpath(local_dir_path, local_path))

            try:
                sftp.stat(remote_dir_path)
                logging.debug(f'Directory exists on remote: {remote_dir_path}')
            except FileNotFoundError:
                logging.info(f'Creating directory: {remote_dir_path}')
                sftp.mkdir(remote_dir_path)

        for filename in files:
            local_file_path = os.path.join(root, filename)
            remote_file_path = os.path.join(remote_path, os.path.relpath(local_file_path, local_path))

            try:
                local_mtime = os.path.getmtime(local_file_path)
                remote_attr = sftp.stat(remote_file_path)
                remote_mtime = remote_attr.st_mtime
                logging.debug(f'Comparing {local_file_path} (local mtime: {local_mtime}) with {remote_file_path} (remote mtime: {remote_mtime})')
                if local_mtime > remote_mtime:
                    logging.info(f'Uploading updated file: {local_file_path} to {remote_file_path}')
                    sftp.put(local_file_path, remote_file_path)
                else:
                    logging.debug(f'Skipping file: {local_file_path}, no update needed')
            except FileNotFoundError:
                logging.info(f'Uploading new file: {local_file_path} to {remote_file_path}')
                sftp.put(local_file_path, remote_file_path)
            except Exception as e:
                logging.error(f'Error synchronizing file {local_file_path}: {e}')
    logging.info('File synchronization (local to remote) complete.')

def sync_files_reverse(sftp, remote_path, local_path):
    """Synchronize files from remote to local directory."""
    logging.info('Starting file synchronization (remote to local)...')
    def sync_remote_dir(remote_dir, local_dir):
        os.makedirs(local_dir, exist_ok=True)
        for entry in sftp.listdir_attr(remote_dir):
            remote_file_path = os.path.join(remote_dir, entry.filename)
            local_file_path = os.path.join(local_dir, entry.filename)

            if S_ISDIR(entry.st_mode):
                sync_remote_dir(remote_file_path, local_file_path)
            else:
                try:
                    remote_mtime = entry.st_mtime
                    local_mtime = os.path.getmtime(local_file_path)
                    logging.debug(f'Comparing {local_file_path} (local mtime: {local_mtime}) with {remote_file_path} (remote mtime: {remote_mtime})')
                    if remote_mtime > local_mtime:
                        logging.info(f'Downloading updated file: {remote_file_path} to {local_file_path}')
                        sftp.get(remote_file_path, local_file_path)
                    else:
                        logging.debug(f'Skipping file: {remote_file_path}, no update needed')
                except FileNotFoundError:
                    logging.info(f'Downloading new file: {remote_file_path} to {local_file_path}')
                    sftp.get(remote_file_path, local_file_path)
                except Exception as e:
                    logging.error(f'Error synchronizing file {remote_file_path}: {e}')

    sync_remote_dir(remote_path, local_path)
    logging.info('File synchronization (remote to local) complete.')

def job():
    """Job to be scheduled for file synchronization."""
    try:
        ssh = ssh_connect()
        sftp = sftp_connect(ssh)
        sync_files(sftp, local_dir, remote_dir)
        sync_files_reverse(sftp, remote_dir, local_dir)
        sftp.close()
        ssh.close()
    except Exception as e:
        logging.error(f'Error during synchronization job: {e}')

# Schedule the job every 10 minutes
logging.info('Scheduling the synchronization job to run every 10 minutes...')
schedule.every(0.1).minutes.do(job)

# Run the job once at startup
logging.info('Running the synchronization job at startup...')
job()

# Run the scheduler
logging.info('Starting the scheduler...')
while True:
    schedule.run_pending()
    time.sleep(1)
