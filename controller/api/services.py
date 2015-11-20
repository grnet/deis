import json
import logging
import random
import string

logger = logging.getLogger(__name__)


def mkrandom(size=32, digits=True, punctuation=True):
    voc = string.ascii_letters
    if digits:
        voc += string.digits
    if punctuation:
        voc += string.punctuation
    return ''.join([random.choice(voc) for n in xrange(32)])


class Service(object):

    keys = []

    def __init__(self, config=None, params=None, client=None):
        self.config = config
        self.params = params
        self.client = client

    def validate(self, value):
        value = value.strip()
        value = json.loads(value)
        return json.dumps(value)

    def set_keys(self, keys):
        for key in keys.keys():
            if key in ['PG_DATABASE_HOST', 'PG_DATABASE_PORT']:
                self.config.values[key] = keys[key]
            if key not in self.config.values:
                self.config.values[key] = keys[key]

    def get_keys(self):
        keys = {}
        values = self.config.values
        for key in self.keys:
            if key in values:
                keys[key] = values.get(key)
        return keys

    def optout(self):
        for key in self.keys:
            if key in self.config.values:
                del self.config.values[key]

    def register(self):
        app = self.config.app
        logger.info("Register {} for {}".format(self.name, app))
        keys = self.setup()
        self.set_keys(keys)
        return self.get_keys()


class PGService(Service):
    name = 'postgresql'
    key_prefix = 'PG_'
    keys = ['PG_DATABASE_NAME',
            'PG_DATABASE_USER',
            'PG_DATABASE_PASSWORD',
            'PG_DATABASE_HOST',
            'PG_DATABASE_PORT',
            'DATABASE_URL']

    def setup(self):
        app_id = str(self.config.app.id)
        user = mkrandom(8, digits=False, punctuation=False)
        password = mkrandom(32, punctuation=False)
        db = mkrandom(8, digits=False, punctuation=False).lower()

        user = "user_{}_{}".format(app_id, user).replace('-', '_').lower()
        db = "appdb_{}_{}".format(app_id, db).replace('-', '_').lower()
        port = None
        host = None
        if self.client:
            port = self.client.get('/deis/database/port').value
            host = self.client.get('/deis/database/host').value

        db_url = "psql://%s:%s@%s:%s/%s" % (user, password, host, port, db)
        return {
            'PG_DATABASE_PORT': port,
            'PG_DATABASE_HOST': host,
            'PG_DATABASE_NAME': db,
            'PG_DATABASE_USER': user,
            'PG_DATABASE_PASSWORD': password,
            'DATABASE_URL': db_url
        }


class REDISService(Service):
    name = 'redis'
    key_prefix = 'REDIS'


def _fill_config(client, **kwargs):
    config = kwargs.get('instance')
    registered = []
    for key, value in config.values.items():
        if key in SERVICES.keys():
            try:
                params = json.loads(value)
            except:
                params = {}
            try:
                service = SERVICES[key](config, params, client=client)
                config.values.update(service.register())
                registered.append(key)
            except Exception, e:
                logger.exception(e)

    for key, service in SERVICES.iteritems():
        if key in registered:
            continue
        service = SERVICES[key](config, {}).optout()


SERVICES = {
    'PG': PGService,
    'REDIS': REDISService
}

PRESERVED_KEYS = reduce(lambda a, b: a + [b.key_prefix], SERVICES.values(), [])
