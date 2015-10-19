# Astakos authentication backend

from django.contrib.auth.models import User
from rest_framework.authtoken.views import \
    ObtainAuthToken as RestObtainAuthToken, \
    AuthTokenSerializer, Response
from astakosclient import AstakosClient, AstakosClientException
from django.core.exceptions import PermissionDenied
from django.conf import settings

ASTAKOS_AUTH_URL = settings.ASTAKOS_AUTH_URL
ACCESS_GROUPS = settings.ASTAKOS_ACCESS_GROUPS


class ObtainAuthToken(RestObtainAuthToken):

    def post(self, request):
        serializer = AuthTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = request.data.get('password')
        return Response({'token': token})

obtain_auth_token = ObtainAuthToken.as_view()


class AstakosBackend(object):

    def authenticate(self, username=None, password=None):
        client = AstakosClient(password, ASTAKOS_AUTH_URL)
        try:
            astakos_user = client.authenticate()
        except AstakosClientException:
            if len(username) == 36:
                raise PermissionDenied("Permission denied")
            return None

        user_data = astakos_user.get('access')
        token_data = user_data.get('token')
        user_data = user_data.get('user')
        tenant = user_data.get('id')
        email = client.get_username(tenant)
        email = "%s-%s" % (tenant, email)

        if ACCESS_GROUPS:
            groups = astakos_user.get('access').get('user').get('roles', [])
            groups = map(lambda x: x.get('name'), groups)
            has_access = any(map(lambda x: x in ACCESS_GROUPS, groups))
            if not has_access:
                raise PermissionDenied("Permission denied")
                return None

        user, created = User.objects.get_or_create(username=tenant, email=email)
        user.set_password(token_data.get('id'))
        user.is_active = True
        user.email = email
        user.save()
        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
