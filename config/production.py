from config.default import *

SQLALCHEMY_DATABASE_URI ='sqlite:///{}'.format(os.path.join(BASE_DIR, 'pybo.db'))
SQLALCHEMY_TRACK_MODIFICATIONS = False
SECRET_KEY = b'\xb0P\x9b\x08;B\xfc$k\xdarL\x88Ky\x94'