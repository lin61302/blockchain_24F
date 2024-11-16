import os
import shutil
import subprocess
import re

project_name = "source"

def strip_ansi_codes(s):
    """
        forge outputs text with ANSI codes for color
        We need to strip them out to get the latex regexes to work
    """
    return re.sub(r'\x1b\[([0-9,A-Z]{1,2}(;[0-9]{1,2})?(;[0-9]{3})?)?[m|K]?', '', s)


def validate(dir_string, retry=0):
    test_path = os.path.dirname(os.path.abspath(__file__)) + f"/{project_name}" #Where the foundry test files live
    student_files = ['Source.sol']

    if not os.path.isdir(f"{test_path}/src/"):
        print( f"Error: {test_path}/src/ is not a directory" )
        print( "Please contact your instructor" )
        return 0

    for f in student_files:
        prefixes = [dir_string,f"{dir_string}/{project_name}",f"{dir_string}/{project_name}/src"]
        for p in prefixes:
            try:
                shutil.copyfile(f"{p}/{f}",f"{test_path}/src/{f}")
            except Exception as e:
                pass
        if not os.path.isfile(f"{test_path}/src/{f}"):
            print( f"Failed to copy file {f}" )
            print( f"Searched in {prefixes}" )
            print( f"Are you sure it's in your repository?" )

    num_passed = num_failed = 0
    max_retries = 3
    forge_failed = False
    try:
        proc = subprocess.check_output( ['forge','test'], cwd=test_path )
    except subprocess.CalledProcessError as e:
        if e.returncode == 1: #If some forge tests fail, forge returns with code 1
            forge_failed = True #We need to note this because when forge fails, its output is different
            proc = e.output
        else:
            return 0
    except Exception as e:
        if retry < max_retries:
            return validate( dir_string, retry=retry+1)
        else:
            print( "Could not run 'forge test'" )
            return 0

    output = strip_ansi_codes( proc.decode('utf-8').splitlines()[-1] )
    if forge_failed:
        rmatch = re.search('(\d+) tests succeeded', output )
        if rmatch:
            num_passed = int(rmatch.group(1))
            print( f"num_passed = {num_passed}" )
        rmatch = re.search('(\w+) failing tests', output )
        if rmatch:
            num_failed= int(rmatch.group(1))
            print( f"num_failed = {num_failed}" )
    else:
        rmatch = re.search('(\d+) passed', output )
        if rmatch:
            num_passed = int(rmatch.group(1))
            print( f"num_passed = {num_passed}" )
        rmatch = re.search('(\d+) failed', output )
        if rmatch:
            num_failed= int(rmatch.group(1))
            print( f"num_failed = {num_failed}" )


    score = 0
    if num_passed + num_failed > 0:
        score = (100.0*num_passed)/(num_passed+num_failed)

    print( f"Score = {score}" )
    return score
 

if __name__ == '__main__':
    validate(f"/home/codio/workspace/{project_name}/src/")

