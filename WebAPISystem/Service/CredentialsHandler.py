import types
from DIRAC import S_OK, S_ERROR
from DIRAC.Core.DISET.RequestHandler import RequestHandler
from DIRAC.Core.Security import Properties
from WebAPIDIRAC.WebAPISystem.DB.CredentialsDB import CredentialsDB

class CredentialsHandler( RequestHandler ):

  @classmethod
  def initializeHandler( cls, serviceInfoDict ):
    cls.__credDB = CredentialsDB()
    return S_OK()


  ##
  # Consumer management
  ##

  auth_generateConsumerPair = [ Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR ]
  types_generateConsumerPair = [ types.StringTypes, types.StringTypes, types.StringTypes ]
  def export_generateConsumerPair( self, name, callback, icon, consumerKey = "" ):
    return self.__credDB.generateConsumerPair( name, callback, icon, consumerKey )

  auth_getConsumerData = [ Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR ]
  types_getConsumerData = [ types.StringTypes ]
  def export_getConsumerData( self, consumerKey ):
    return self.__credDB.getConsumerData( consumerKey )

  auth_deleteConsumer = [ Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR ]
  types_deleteConsumer = [ types.StringTypes ]
  def export_deleteConsumer( self, consumerKey ):
    return self.__credDB.deleteConsumer( consumerKey )

  auth_getAllConsumers = [ Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR ]
  types_getAllConsumers = []
  def export_getAllConsumers( self ):
    return self.__credDB.getAllConsumers()


  ##
  # Request management
  ##

  auth_generateRequest = [ Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR ]
  types_generateRequest = [ types.StringTypes, types.StringTypes ]
  def export_generateRequest( self, consumerKey, callback ):
    return self.__credDB.generateRequest( consumerKey, callback )

  auth_getRequestData = [ Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR ]
  types_getRequestData = [ types.StringTypes ]
  def export_getRequestData( self, request ):
    return self.__credDB.getRequestData( request )

  auth_deleteRequest = [ Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR ]
  types_deleteRequest = [ types.StringTypes ]
  def export_deleteRequest( self, request ):
    return self.__credDB.deleteRequest( request )

  ##
  # Verifier management
  ##

  auth_generateVerifier = [ Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR ]
  types_generateVerifier = ( types.StringTypes, types.StringTypes,
                             types.StringTypes, types.StringTypes,
                            ( types.IntType, types.LongType ) )
  def export_generateVerifier( self, consumerKey, request, userDN, userGroup, lifeTime ):
    return self.__credDB.generateVerifier( consumerKey, request, userDN, userGroup, lifeTime )

  auth_getVerifierData = [ Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR ]
  types_getVerifierData = ( types.StringTypes, )
  def export_getVerifierData( self, verifier ):
    return self.__credDB.getVerifierData( verifier )

  auth_deleteVerifier = [ Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR ]
  types_deleteVerifier = ( types.StringTypes, )
  def export_deleteVerifier( self, verifier ):
    return self.__credDB.deleteVerifier( verifier )

  auth_findVerifier = [ Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR ]
  types_findVerifier = ( types.StringTypes, types.StringTypes )
  def export_findVerifier( self, consumerKey, request ):
    return self.__credDB.findVerifier( consumerKey, request )

  auth_setVerifierProperties = [ Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR ]
  types_setVerifierProperties = ( types.StringTypes, types.StringTypes, types.StringTypes,
                                  types.StringTypes, types.StringTypes,
                                  ( types.IntType, types.LongType ) )
  def export_setVerifierProperties( self, consumerKey, request, verifier,
                                          userDN, userGroup, lifeTime ):
    return self.__credDB.setVerifierProperties( consumerKey, request, verifier,
                                                userDN, userGroup, lifeTime )


  ##
  # Token management
  ##


  auth_generateToken = [ Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR ]
  types_generateToken = ( types.StringTypes, types.StringTypes, types.StringTypes )
  def export_generateToken( self, consumerKey, request, verifier ):
    return self.__credDB.generateToken( consumerKey, request, verifier )

  auth_getTokenData = [ Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR ]
  types_getTokenData = ( types.StringTypes, types.StringTypes )
  def export_getTokenData( self, consumerKey, token ):
    return self.__credDB.getTokenData( consumerKey, token )

  auth_revokeUserToken = [ Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR ]
  types_revokeUserToken = [ types.StringTypes, types.StringTypes, types.StringTypes ]
  def export_revokeUserToken( self, userDN, userGroup, token ):
    return self.__credDB.revokeUserToken( userDN, userGroup, token )

  auth_revokeToken = [ Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR, 'all' ]
  types_revokeToken = [ types.StringTypes ]
  def export_revokeToken( self, token ):
    credDict = self.srv_getRemoteCredentials()
    for prop in ( Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR ):
      if prop in credDict[ 'properties' ]:
        return self.__credDB.revokeToken( token )
    return self.__credDB.revokeToken( credDict[ 'DN' ], credDict[ 'group' ], token )

  auth_getTokens = [ Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR ]
  types_getTokens = [ types.DictType ]
  def export_getTokens( self, condDict ):
    return self.__credDB.getTokens( condDict )


  ##
  # Cleaning
  ##

  auth_cleanExpired = [ Properties.TRUSTED_HOST, Properties.SERVICE_ADMINISTRATOR ]
  types_cleanExpired = []
  def export_cleanExpired( self, minLifeTime = 0 ):
    try:
      minLifeTime = max( 0, int( minLifeTime ) )
    except ValueError:
      return S_ERROR( "Minimun life time has to be an integer " )
    return self.__credDB.cleanExpired( minLifeTime )
