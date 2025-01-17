import json
import valkey # type: ignore
import tempfile
import os
from git import Repo

from ransomlook.default.config import get_config, get_socket_path

def main() -> None :
    gitrepo = 'https://github.com/threatlabz/ransomware_notes'
    valkey_handle = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=11)

    with tempfile.TemporaryDirectory() as tmpdirname:
        Repo.clone_from(gitrepo, tmpdirname)
        rootdir = tmpdirname
        for folder in os.listdir(rootdir):
            if folder.startswith('.'):
                continue
            data=[]
            d = os.path.join(rootdir, folder)
            if os.path.isdir(d):
                key = os.path.dirname(d)
                for file in os.listdir(d):
                    f = os.path.join(d, file)
                    if os.path.isfile(f):
                        myfile = open(f,mode='r')
                        try : 
                            content = myfile.read()
                            data.append({'name':file,'content':content})
                        except :
                            pass
                        myfile.close()
            if data :
                valkey_handle.set(folder.lower(), json.dumps(data))

if __name__ == '__main__':
    main()
