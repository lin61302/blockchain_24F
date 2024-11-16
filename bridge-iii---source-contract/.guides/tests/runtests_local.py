#!/usr/bin/env python3
import os
import pygit2
import shutil
from pathlib import Path
import sys

try:
    from validate import validate
except ImportError:
    raise ImportError("Unable import validation script")

def clone_student_repo(test_dir):
# Get the students' github username and name of repository
    try:
        credentials_folder = "/home/codio/workspace/student_credentials"
        with open(credentials_folder, "r") as f:
            github_username, DIR = f.readlines()
            github_username, DIR = github_username.strip(), DIR.strip()
    except Exception as e:
        print( "Error: could not open credentials folder" )
        print( f"Make sure the folder \"{credentials_folder}\" exists" )
        sys.exit(1)

    # Clear any existing directory (clone_respository will fail otherwise)
    dir_string = f'/home/codio/workspace/.guides/{test_dir}/student_code/{DIR}'
    dir_path = Path(dir_string)
    try:
        if dir_path.exists():
            shutil.rmtree(dir_path)
    except OSError as e:
        print("Error when removing directory: %s : %s" % (dir_path, e.strerror))

    key_dir = "/home/codio/workspace/ssh_keys"
    key_file = "id_mcit5830"

    if not Path(f"{key_dir}/{key_file}").is_file() or not Path(f"{key_dir}/{key_file}.pub").is_file():
        print( f"Error can't find SSH keys!" )
        print( f"Make sure \"{key_dir}/{key_file}\" and \"{key_dir}/{key_file}.pub\" exist" )
        sys.exit(1)

    try:
        # import student code using pygit2
        keypair = pygit2.Keypair("git", f"{key_dir}/{key_file}.pub", f"{key_dir}/{key_file}", "")
        callbacks = pygit2.RemoteCallbacks(credentials=keypair)
        print(f'Cloning from: git@github.com:{github_username}/{DIR}.git')
        pygit2.clone_repository(f"git@github.com:{github_username}/{DIR}.git", dir_string, callbacks=callbacks)
        sys.path.append(dir_string)
    except:
        print("Failed to clone the repository.")
        sys.exit(1)

    return dir_string

# Get the url to send the results to
def main():
    if os.path.basename(__file__) == 'autograde.py':
      test_dir = "secure"
    else:
      test_dir = "tests"

    if os.path.basename(__file__) != 'runtests_local.py':
        code_path = clone_student_repo(test_dir)
    else:
        #sys.path.append("/home/codio/workspace/")
        print( f"Running tests locally (no git clone)" )
        code_path = "/home/codio/workspace"

    # Execute the test on the student's code
    grade = validate(code_path)

    if os.path.basename(__file__) == 'autograde.py':
        # Send the grade back to Codio 
        CODIO_AUTOGRADE_URL = os.environ["CODIO_AUTOGRADE_URL"]
        CODIO_UNIT_DATA = os.environ["CODIO_AUTOGRADE_ENV"]
        # import grade submit function
        sys.path.append('/usr/share/codio/assessments')
        from lib.grade import send_grade
        res = send_grade(int(round(grade)))
        sys.exit(0)
    if os.path.basename(__file__) == 'runtests.py' or os.path.basename(__file__) == 'runtests_local.py':
        print( f"Score would be {grade}" )
        sys.exit(0)
    print( f"Unknown file name -- please contact your instructor" )
    print( f"Score would be {grade}" )

main()
