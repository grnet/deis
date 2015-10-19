from django.contrib.auth.models import User
from astakosclient import AstakosClient, AstakosClientException
from django.conf import settings
from rest_framework.authentication import \
    TokenAuthentication as RestTokenAuthentication, \
    exceptions

ASTAKOS_AUTH_URL = settings.ASTAKOS_AUTH_URL
ACCESS_GROUPS = settings.ASTAKOS_ACCESS_GROUPS


class TokenAuthentication(RestTokenAuthentication):

    def authenticate_credentials(self, key):
        client = AstakosClient(key, ASTAKOS_AUTH_URL)
        try:
            auth = client.authenticate()
        except AstakosClientException, e:
            raise exceptions.AuthenticationFailed(e.message)

        tenant = auth.get('access').get('user').get('id')
        try:
            user = User.objects.get(username=tenant, is_active=True)
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('User does not exist')

        email = client.get_username(tenant)
        email = "%s-%s" % (tenant, email)
        user.email = email

        if ACCESS_GROUPS:
            groups = auth.get('access').get('user').get('roles', [])
            groups = map(lambda x: x.get('name'), groups)
            has_access = any(map(lambda x: x in ACCESS_GROUPS, groups))
            if not has_access:
                user.is_active = False
                user.save()
                raise exceptions.AuthenticationFailed('Permission denied')

        user.save()
        return (user, key)
