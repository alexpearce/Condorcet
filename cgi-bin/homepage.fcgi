#!/afs/cern.ch/user/g/gdujany/www/Condorcet/venv/bin/python
import sys
base = '/afs/cern.ch/user/g/gdujany/www/Condorcet'
sys.path.insert(0,base+'/flup-1.0.2-py2.6.egg')
sys.path.insert(0,base)
sys.path.insert(0,base+'/Condorcet')

from flup.server.fcgi import WSGIServer
from Condorcet import app

if __name__ == '__main__':
    WSGIServer(app).run()