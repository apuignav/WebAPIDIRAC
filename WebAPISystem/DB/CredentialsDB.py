########################################################################
# $HeadURL$
########################################################################
""" ProxyRepository class is a front-end to the proxy repository Database
"""

__RCSID__ = "$Id$"

import time
import sys
import random
try:
  import hashlib as md5
except:
  import md5
from DIRAC  import gConfig, gLogger, S_OK, S_ERROR
from DIRAC.Core.Base.DB import DB

class CredentialsDB( DB ):

  VALID_OAUTH_TOKEN_TYPES = ( "request", "access" )

  def __init__( self, maxQueueSize = 10 ):
    DB.__init__( self, 'CredentialsDB', 'WebAPI/CredentialsDB', maxQueueSize )
    random.seed()
    retVal = self.__initializeDB()
    if not retVal[ 'OK' ]:
      raise Exception( "Can't create tables: %s" % retVal[ 'Message' ] )

  def __initializeDB( self ):
    """
    Create the tables
    """
    retVal = self._query( "show tables" )
    if not retVal[ 'OK' ]:
      return retVal

    tablesInDB = [ t[0] for t in retVal[ 'Value' ] ]
    tablesD = {}

    if 'CredDB_OATokens' not in tablesInDB:
      tablesD[ 'CredDB_OATokens' ] = { 'Fields' : { 'Token' : 'CHAR(32) NOT NULL UNIQUE',
                                                    'Secret' : 'CHAR(32) NOT NULL',
                                                    'ConsumerKey' : 'VARCHAR(64) NOT NULL',
                                                    'UserId' : 'INT UNSIGNED NOT NULL',
                                                    'ExpirationTime' : 'DATETIME',
                                                },
                                      'PrimaryKey' : 'Token',
                                      'Indexes' : { 'Expiration' : [ 'ExpirationTime' ] }
                                    }

    if 'CredDB_OARequests' not in tablesInDB:
      tablesD[ 'CredDB_OARequests' ] = { 'Fields' : { 'Request' : 'CHAR(32) NOT NULL UNIQUE',
                                                      'Secret' : 'CHAR(32) NOT NULL',
                                                      'ConsumerKey' : 'VARCHAR(64) NOT NULL',
                                                      'Callback' : 'VARCHAR(128) NOT NULL DEFAULT ""',
                                                      'ExpirationTime' : 'DATETIME',
                                                },
                                        'PrimaryKey' : 'Request',
                                        'Indexes' : { 'Expiration' : [ 'ExpirationTime' ] }
                                      }

    if 'CredDB_Identities' not in tablesInDB:
      tablesD[ 'CredDB_Identities' ] = { 'Fields' : { 'Id' : 'INT UNSIGNED AUTO_INCREMENT NOT NULL',
                                                      'UserDN' : 'VARCHAR(255) NOT NULL',
                                                      'UserGroup' : 'VARCHAR(255) NOT NULL',
                                                  },
                                      'PrimaryKey' : 'Id',
                                      'UniqueIndexes' : { 'Identity' : [ 'UserDN', 'UserGroup' ] }
                                     }

    if 'CredDB_OAVerifier' not in tablesInDB:
      tablesD[ 'CredDB_OAVerifier' ] = { 'Fields' : { 'Verifier' : 'CHAR(32) NOT NULL',
                                                      'UserId' : 'INT UNSIGNED NOT NULL',
                                                      'ConsumerKey' : 'VARCHAR(255) NOT NULL',
                                                      'Request' : 'CHAR(32) NOT NULL',
                                                      'ExpirationTime' : 'DATETIME'
                                                  },
                                      'PrimaryKey' : 'Verifier',
                                     }

    if 'CredDB_OAConsumers' not in tablesInDB:
      tablesD[ 'CredDB_OAConsumers' ] = { 'Fields' : { 'ConsumerKey' : 'VARCHAR(64) NOT NULL UNIQUE',
                                                       'Secret' : 'CHAR(32) NOT NULL',
                                                       'Name' : 'VARCHAR(64) NOT NULL',
                                                       'Callback' : 'VARCHAR(128) NOT NULL DEFAULT ""',
                                                       'Icon' : 'VARCHAR(128) DEFAULT ""'
                                                  },
                                      'PrimaryKey' : 'ConsumerKey',
                                     }

    return self._createTables( tablesD )

  #############################
  #
  #     Consumers
  #
  #############################

  def generateConsumerPair( self, name, callback, icon, consumerKey = "" ):
    if not consumerKey:
      consumerKey = '%s' % md5.md5( "%s|%s|%s|%s|%s" % ( name, callback, icon, time.time(), random.random() ) ).hexdigest()
      sqlConsumerKey = '"%s"' % consumerKey
    else:
      if len( consumerKey ) > 64 or len( consumerKey ) < 5:
        return S_ERROR( "Consumer key doesn't have a correct size" )
      result = self._escapeString( consumerKey )
      if not result[ 'OK' ]:
        return result
      sqlConsumerKey = result[ 'Value' ]
    secret = md5.md5( "%s|%s|%s" % ( consumerKey, time.time(), random.random() ) ).hexdigest()
    sqlSecret = '"%s"' % secret
    result = self._escapeString( name )
    if not result[ 'OK' ]:
      return result
    sqlName = result[ 'Value' ]
    result = self._escapeString( callback )
    if not result[ 'OK' ]:
      return result
    sqlCallback = result[ 'Value' ]
    result = self._escapeString( icon )
    if not result[ 'OK' ]:
      return result
    sqlIcon = result[ 'Value' ]

    sqlFields = "( Name, Callback, Icon, ConsumerKey, Secret )"
    sqlValues = ( sqlName, sqlCallback, sqlIcon, sqlConsumerKey, sqlSecret )
    sqlIn = "INSERT INTO `CredDB_OAConsumers` %s VALUES ( %s )" % ( sqlFields, ",".join( sqlValues ) )
    result = self._update( sqlIn )
    if not result[ 'OK' ]:
      if result[ 'Message' ].find( "Duplicate entry" ):
        return S_ERROR( "Consumer already exists" )
      return result
    consData = { 'key' : consumerKey,
                 'secret' : secret,
                 'name' : name,
                 'callback' : callback,
                 'icon' : icon }
    return S_OK( consData )

  def getConsumerData( self, consumerKey ):
    if len( consumerKey ) > 64 or len( consumerKey ) < 5:
      return S_ERROR( "Consumer key doesn't have a correct size" )
    result = self._escapeString( consumerKey )
    if not result[ 'OK' ]:
      return result
    sqlConsumerKey = result[ 'Value' ]
    sqlCmd = "SELECT Secret, Name, Callback, Icon FROM `CredDB_OAConsumers` WHERE ConsumerKey = %s" % sqlConsumerKey
    result = self._query( sqlCmd )
    if not result[ 'OK' ]:
      return result
    data = result[ 'Value' ]
    if len( data ) < 1:
      return S_ERROR( "Unknown consumer" )
    cData = data[0]
    consData = { 'key' : consumerKey,
                 'secret' : cData[0],
                 'name' : cData[1],
                 'callback' : cData[2],
                 'icon' : cData[3] }
    return S_OK( consData )

  def deleteConsumer( self, consumerKey ):
    if len( consumerKey ) > 64 or len( consumerKey ) < 5:
      return S_ERROR( "Consumer key doesn't have a correct size" )
    result = self._escapeString( consumerKey )
    if not result[ 'OK' ]:
      return result
    sqlConsumerKey = result[ 'Value' ]
    totalDeleted = 0
    for table in ( "OAConsumers", "OAVerifier", "OATokens" ):
      sqlCmd = "DELETE FROM `CredDB_%s` WHERE ConsumerKey = %s" % ( table, sqlConsumerKey )
      result = self._update( sqlCmd )
      if not result[ 'OK' ]:
        return result
      totalDeleted += result[ 'Value' ]
    return S_OK( totalDeleted )

  def getAllConsumers( self ):
    sqlCmd = "SELECT Name, Callback, ConsumerKey, Secret, Icon FROM `CredDB_OAConsumers`"
    result = self._query( sqlCmd )
    if not result[ 'OK' ]:
      return result
    return S_OK( { 'Parameters' : [ 'name', 'callback', 'key', 'secret', 'icon' ],
                   'Records' : result[ 'Value' ] } )

  #############################
  #
  #     Requests
  #
  #############################

  def generateRequest( self, consumerKey, callback = "", lifeTime = 900 ):
    result = self.getConsumerData( consumerKey )
    if not result[ 'OK' ]:
      return result
    consData = result[ 'Value' ]
    if not consData[ 'callback' ] and not callback:
      return S_ERROR( "Neither Consumer nor request have a callback defined" )
    result = self.__generateRequest( consumerKey, callback, lifeTime )
    if not result[ 'OK' ]:
      return result
    reqData = result[ 'Value' ]
    reqData[ 'consumer' ] = consData
    if not reqData[ 'callback' ]:
      reqData[ 'callback' ] = consData[ 'callback' ]
    return result

  def __generateRequest( self, consumerKey, callback, lifeTime, retries = 5 ):
    request = md5.md5( "%s|%s|%s" % ( consumerKey, time.time(), random.random() ) ).hexdigest()
    secret = md5.md5( "%s|%s|%s" % ( request, time.time(), random.random() ) ).hexdigest()
    if len( consumerKey ) > 64 or len( consumerKey ) < 5:
      return S_ERROR( "Consumer key doesn't have a correct size" )
    result = self._escapeString( consumerKey )
    if not result[ 'OK' ]:
      return result
    sqlConsumerKey = result[ 'Value' ]

    sqlFields = [ "Request", "Secret", "ConsumerKey", "ExpirationTime" ]
    sqlValues = [ "'%s'" % request, "'%s'" % secret, sqlConsumerKey,
                 "TIMESTAMPADD( SECOND, %d, UTC_TIMESTAMP() )" % lifeTime ]

    if callback:
      result = self._escapeString( callback )
      if not result[ 'OK' ]:
        return result
      sqlFields.append( "Callback" )
      sqlValues.append( result[ 'Value' ] )

    sqlIn = "INSERT INTO `CredDB_OARequests` ( %s ) VALUES ( %s )" % ( ",".join( sqlFields ),
                                                                       ",".join( sqlValues ) )
    result = self._update( sqlIn )
    if not result[ 'OK' ]:
      if result[ 'Message' ].find( "Duplicate key" ) > -1 and retries > 0 :
        return self.__generateRequest( consumerKey, callback, lifeTime, retries - 1 )
      return result
    result = S_OK( { 'request' : request,
                     'secret' : secret,
                     'callback' : callback } )
    result[ 'lifeTime' ] = lifeTime
    return result

  def getRequestData( self, request ):

    result = self._escapeString( request )
    if not result[ 'OK' ]:
      self.logger.error( result[ 'Value' ] )
      return result
    sqlRequest = result[ 'Value' ]

    sqlCond = [ "TIMESTAMPDIFF( SECOND, UTC_TIMESTAMP(), ExpirationTime ) > 0" ]
    sqlCond.append( "Request=%s" % sqlRequest )
    sqlSel = "SELECT Secret, ConsumerKey, Callback, TIMESTAMPDIFF( SECOND, UTC_TIMESTAMP(), ExpirationTime ) FROM `CredDB_OARequests` WHERE %s" % " AND ".join( sqlCond )
    result = self._query( sqlSel )
    if not result[ 'OK' ]:
      return result
    data = result[ 'Value' ]
    if len( data ) == 0:
      return S_ERROR( "Request is either unknown or invalid" )

    reqData = { 'request' : request,
                'secret' : data[0][0],
                'callback' : data[0][2] }

    result = self.getConsumerData( data[0][1] )
    if not result[ 'OK' ]:
      return result
    consData = result[ 'Value' ]
    reqData[ 'consumer' ] = consData
    if not reqData[ 'callback' ]:
      reqData[ 'callback' ] = consData[ 'callback' ]

    result = S_OK( reqData )
    result[ 'lifeTime' ] = data[0][3]
    return result


  def deleteRequest( self, request ):
    result = self._escapeString( request )
    if not result[ 'OK' ]:
      return result
    sqlCmd = "DELETE FROM `CredDB_OARequests` WHERE Request=%s" % result[ 'Value' ]
    return self._update( sqlCmd )

  #############################
  #
  #     User ID
  #
  #############################

  def getIdentityId( self, userDN, userGroup, autoInsert = True ):
    sqlDN = self._escapeString( userDN )[ 'Value' ]
    sqlGroup = self._escapeString( userGroup )[ 'Value' ]
    sqlQuery = "SELECT Id FROM `CredDB_Identities` WHERE UserDN=%s AND UserGroup=%s" % ( sqlDN, sqlGroup )
    result = self._query( sqlQuery )
    if not result[ 'OK' ]:
      return result
    data = result[ 'Value' ]
    if len( data ) > 0 and len( data[0] ) > 0:
      return S_OK( data[0][0] )
    if not autoInsert:
      return S_ERROR( "Could not retrieve identity %s@%s" % ( userDN, userGroup ) )
    sqlIn = "INSERT INTO `CredDB_Identities` ( Id, UserDN, UserGroup ) VALUES (0, %s, %s)" % ( sqlDN, sqlGroup )
    result = self._update( sqlIn )
    if not result[ 'OK' ]:
      if result[ 'Message' ].find( "Duplicate key" ) > -1:
        return self.__getIdentityId( userDN, userGroup, autoInsert = False )
      return result
    if 'lastRowId' in result:
      return S_OK( result['lastRowId'] )
    return self.__getIdentityId( userDN, userGroup, autoInsert = False )

  def __getUserAndGroup( self, userId ):
    sqlCmd = "SELECT UserDN, UserGroup FROM `CredDB_Identities` WHERE Id = %d" % userId
    result = self._query( sqlCmd )
    if not result[ 'OK' ]:
      return result
    data = result[ 'Value' ]
    if len( data ) < 1 or len( data[0] ) < 1:
      self.logger.error( "This is incoherent!!! UserId = %d has no identity" % userId )
      return S_ERROR( "Unknown user!" )
    return S_OK( data[0] )

  #############################
  #
  #     Verifier
  #
  #############################

  def generateVerifier( self, consumerKey, request, userDN, userGroup, lifeTime = 3600, retries = 5 ):
    result = self.getConsumerData( consumerKey )
    if not result[ 'OK' ]:
      return result
    result = self.getIdentityId( userDN, userGroup )
    if not result[ 'OK' ]:
      self.logger.error( result[ 'Value' ] )
      return result
    userId = result[ 'Value' ]
    verifier = md5.md5( "%s|%s|%s|%s" % ( userId, consumerKey, time.time(), random.random() ) ).hexdigest()
    if len( consumerKey ) > 64 or len( consumerKey ) < 5:
      return S_ERROR( "Consumer key doesn't have a correct size" )
    result = self._escapeString( consumerKey )
    if not result[ 'OK' ]:
      return result
    sqlConsumerKey = result[ 'Value' ]
    result = self._escapeString( request )
    if not result[ 'OK' ]:
      return result
    sqlRequest = result[ 'Value' ]

    sqlFields = "( Verifier, UserId, ConsumerKey, Request, ExpirationTime )"
    sqlValues = [ "'%s'" % verifier, "%d" % userId, sqlConsumerKey, sqlRequest,
                 "TIMESTAMPADD( SECOND, %d, UTC_TIMESTAMP() )" % lifeTime ]
    sqlIn = "INSERT INTO `CredDB_OAVerifier` %s VALUES ( %s )" % ( sqlFields, ",".join( sqlValues ) )
    result = self._update( sqlIn )
    if not result[ 'OK' ]:
      if result[ 'Message' ].find( "Duplicate key" ) > -1 and retries > 0 :
        return self.generateVerifier( userDN, userGroup, consumerKey, lifeTime, retries - 1 )
      return result
    return S_OK( verifier )

  def __verifierCondition( self, consumerKey = "", request = "", verifier = "" ):
    sqlCond = [ "TIMESTAMPDIFF( SECOND, UTC_TIMESTAMP(), ExpirationTime ) > 0" ]

    if consumerKey:
      if len( consumerKey ) > 64 or len( consumerKey ) < 5:
        return S_ERROR( "Consumer key doesn't have a correct size" )
      result = self._escapeString( consumerKey )
      if not result[ 'OK' ]:
        return result
      sqlConsumerKey = result[ 'Value' ]
      sqlCond.append( "ConsumerKey=%s" % sqlConsumerKey )

    if request:
      result = self._escapeString( request )
      if not result[ 'OK' ]:
        return result
      sqlRequest = result[ 'Value' ]
      sqlCond.append( "Request=%s" % sqlRequest )

    if verifier:
      result = self._escapeString( verifier )
      if not result[ 'OK' ]:
        return result
      sqlVerifier = result[ 'Value' ]
      sqlCond.append( "Verifier=%s" % sqlVerifier )

    return S_OK( sqlCond )

  def getVerifierData( self, verifier ):
    result = self.__verifierCondition( verifier = verifier )
    if not result[ 'OK' ]:
      return result
    sqlCond = result[ 'Value' ]
    sqlFields = [ "UserId", "ConsumerKey", "Request", "TIMESTAMPDIFF( SECOND, UTC_TIMESTAMP(), ExpirationTime )" ]
    sqlCmd = "SELECT %s FROM `CredDB_OAVerifier` WHERE %s" % ( ", ".join( sqlFields ),
                                                              " AND ".join( sqlCond ) )
    result = self._query( sqlCmd )
    if not result[ 'OK' ]:
      return result
    data = result[ 'Value' ]
    if len( data ) == 0:
      return S_ERROR( "Unknown verifier" )
    verData = { 'consumerKey' : data[0][1],
                'request' : data[0][2],
                'lifeTime' : data[0][3],
                'userId' : data[0][0] }
    result = self.__getUserAndGroup( data[0][0] )
    if not result[ 'OK' ]:
      return result
    data = result[ 'Value' ]
    verData[ 'userDN' ] = data[0]
    verData[ 'userGroup' ] = data[1]
    return S_OK( verData )

  def deleteVerifier( self, verifier ):
    result = self.__verifierCondition( verifier = verifier )
    if not result[ 'OK' ]:
      return result
    sqlCond = result[ 'Value' ]
    sqlDel = "DELETE FROM `CredDB_OAVerifier` WHERE %s" % " AND ".join( sqlCond )
    result = self._update( sqlDel )
    if not result[ 'OK' ]:
      return result
    if result[ 'Value' ] < 1:
      return S_ERROR( "Verifier is unknown" )
    return S_OK()

  def findVerifier( self, consumerKey, request ):
    result = self.__verifierCondition( consumerKey, request )
    if not result[ 'OK' ]:
      return result
    sqlCond = result[ 'Value' ]
    sqlFields = [ "Verifier", "TIMESTAMPDIFF( SECOND, UTC_TIMESTAMP(), ExpirationTime )", "UserId" ]
    sqlCmd = "SELECT %s FROM `CredDB_OAVerifier` WHERE %s" % ( ", ".join( sqlFields ), " AND ".join( sqlCond ) )
    result = self._query( sqlCmd )
    if not result[ 'OK' ]:
      return result
    data = result[ 'Value' ]
    if len( data ) < 1 or len( data[0] ) < 1:
      return S_ERROR( "Unknown verifier" )
    verData = { 'verifier' : data[0][0],
                'lifeTime' : data[0][1],
                'userId' : data[0][2] }
    result = self.__getUserAndGroup( data[0][2] )
    if not result[ 'OK' ]:
      return result
    verData[ 'userDN'] = result['Value' ][0]
    verData[ 'userGroup'] = result['Value' ][1]
    return S_OK( verData )

  def setVerifierProperties( self, consumerKey, request, verifier, userDN, userGroup, lifeTime ):
    result = self.getIdentityId( userDN, userGroup )
    if not result[ 'OK' ]:
      self.logger.error( result[ 'Value' ] )
      return result
    userId = result[ 'Value' ]
    sqlUp = [ 'UserId = %d' % userId ]
    try:
      sqlUp.append( "Expirationtime = TIMESTAMPADD( SECOND, %d, UTC_TIMESTAMP() )" % lifeTime )
    except ValueError:
      return S_ERROR( "LifeTime has to be an integer" )
    result = self.__verifierCondition( consumerKey, request )
    if not result[ 'OK' ]:
      return result
    sqlCond = result[ 'Value' ]
    result = self._update( "UPDATE `CredDB_OAVerifier` SET %s WHERE %s" % ( ", ".join( sqlUp ),
                                                                            " AND ".join( sqlCond ) ) )
    if not result[ 'OK' ]:
      return result
    if result[ 'Value' ] == 0:
      return S_ERROR( "Unknown verifier" )
    return result

  #############################
  #
  #     Token
  #
  #############################

  def generateToken( self, consumerKey, request, verifier ):
    result = self.getVerifierData( verifier )
    if not result[ 'OK' ]:
      return result
    verData = result[ 'Value' ]
    if verData[ 'consumerKey' ] != consumerKey or verData[ 'request' ] != request:
      return S_ERROR( "Verifier %s is not associated to this request/consumer" % verifier )
    if verData[ 'lifeTime' ] < 0:
      return S_ERROR( "Life time has to be a positive integer" )
    result = self.__generateToken( verData[ 'userId' ], consumerKey, verData[ 'lifeTime' ] )
    if not result[ 'OK' ]:
      return result
    tokenData = { 'token' : result[ 'Value' ][0],
                  'secret' : result[ 'Value'][1],
                  'userDN' : verData[ 'userDN' ],
                  'userGroup' : verData[ 'userGroup' ],
                  'lifeTime' : verData[ 'lifeTime' ]
                }

    self.deleteVerifier( verifier )

    return S_OK( tokenData )


  def __generateToken( self, userId, consumerKey, lifeTime, retries = 5 ):
    token = md5.md5( "%s|%s|%s|%s|%s" % ( userId, type, consumerKey, time.time(), random.random() ) ).hexdigest()
    secret = md5.md5( "%s|%s|%s|%s" % ( userId, consumerKey, time.time(), random.random() ) ).hexdigest()
    if len( consumerKey ) > 64 or len( consumerKey ) < 5:
      return S_ERROR( "Consumer key doesn't have a correct size" )
    result = self._escapeString( consumerKey )
    if not result[ 'OK' ]:
      return result
    sqlConsumerKey = result[ 'Value' ]

    sqlFields = "( Token, Secret, ConsumerKey, UserId, ExpirationTime )"
    sqlValues = [ "'%s'" % token, "'%s'" % secret, sqlConsumerKey, "%d" % userId,
                 "TIMESTAMPADD( SECOND, %d, UTC_TIMESTAMP() )" % lifeTime ]
    sqlIn = "INSERT INTO `CredDB_OATokens` %s VALUES ( %s )" % ( sqlFields, ",".join( sqlValues ) )
    result = self._update( sqlIn )
    if not result[ 'OK' ]:
      if result[ 'Message' ].find( "Duplicate key" ) > -1 and retries > 0 :
        return self.__generateToken( userId, consumerKey, lifeTime, retries - 1 )
      return result
    return S_OK( ( token, secret ) )

  def getTokenData( self, consumerKey, token ):
    result = self._escapeString( token )
    if not result[ 'OK' ]:
      self.logger.error( result[ 'Value' ] )
      return result
    sqlToken = result[ 'Value' ]

    result = self._escapeString( consumerKey )
    if not result[ 'OK' ]:
      self.logger.error( result[ 'Value' ] )
      return result
    sqlConsumerKey = result[ 'Value' ]

    sqlCond = [ "TIMESTAMPDIFF( SECOND, UTC_TIMESTAMP(), ExpirationTime ) > 0" ]
    sqlCond.append( "Token=%s" % sqlToken )
    sqlCond.append( "ConsumerKey=%s" % sqlConsumerKey )
    sqlSel = "SELECT Secret, TIMESTAMPDIFF( SECOND, UTC_TIMESTAMP(), ExpirationTime ), UserId FROM `CredDB_OATokens` WHERE %s" % " AND ".join( sqlCond )
    result = self._query( sqlSel )
    if not result[ 'OK' ]:
      return result
    data = result[ 'Value' ]
    if len( data ) < 1 or len( data[0] ) < 1:
      return S_ERROR( "Unknown token" )
    tokenData = { 'token' : token,
                  'secret' : data[0][0],
                  'lifeTime' : data[0][1] }
    result = self.__getUserAndGroup( data[0][2] )
    if not result[ 'OK' ]:
      return result
    tokenData[ 'userDN'] = result['Value' ][0]
    tokenData[ 'userGroup'] = result['Value' ][1]
    return S_OK( tokenData )

  def getTokens( self, condDict = {} ):
    sqlTables = [ '`CredDB_OATokens` t', '`CredDB_Identities` i' ]
    sqlCond = [ "t.UserId = i.Id"]

    fields = [ 'Token', 'Secret', 'ConsumerKey', 'UserDN', 'UserGroup' ]
    sqlFields = []
    for field in fields:
      if field in ( 'UserDN', 'UserGroup' ):
        sqlField = "i.%s" % field
      else:
        sqlField = "t.%s" % field
      sqlFields.append( sqlField )
      if field in condDict:
        if type( condDict[ field ] ) not in ( types.ListType, types.TupleType ):
          condDict[ field ] = [ str( condDict[ field ] ) ]
        sqlValues = [ self._escapeString( val )[ 'Value' ] for val in condDict[ field ] ]
        if len( sqlValues ) == 1:
          sqlCond.append( "%s = %s" % ( sqlField, sqlValues[0] ) )
        else:
          sqlCond.append( "%s in ( %s )" % ( sqlField, ",".join( sqlValues[0] ) ) )

    sqlFields.append( "TIMESTAMPDIFF( SECOND, UTC_TIMESTAMP(), ExpirationTime )" )
    fields.append( "LifeTime" )
    sqlCmd = "SELECT %s FROM %s WHERE %s" % ( ", ". join( sqlFields ), ", ".join( sqlTables ), " AND ".join( sqlCond ) )
    result = self._query( sqlCmd )
    if not result[ 'OK' ]:
      return result
    return S_OK( { 'Parameters' : fields, 'Records' : result[ 'Value' ] } )

  def revokeUserToken( self, userDN, userGroup, token ):
    result = self.getIdentityId( userDN, userGroup )
    if not result[ 'OK' ]:
      self.logger.error( result[ 'Value' ] )
      return result
    userId = result[ 'Value' ]
    return self.revokeToken( token, userId )

  def revokeToken( self, token, userId = -1 ):
    result = self._escapeString( token )
    if not result[ 'OK' ]:
      self.logger.error( result[ 'Value' ] )
      return result
    sqlToken = result[ 'Value' ]
    sqlCond = [ "Token=%s" % sqlToken ]
    try:
      userId = int( userId )
    except ValueError:
      return S_ERROR( "userId has to be an integer" )
    if userId > -1:
      sqlCond.append( "userId = %d" % userId )
    sqlDel = "DELETE FROM `CredDB_OATokens` WHERE %s" % " AND ".join( sqlCond )
    return self._update( sqlDel )



  def cleanExpired( self, minLifeTime = 0 ):
    try:
      minLifeTime = int( minLifeTime )
    except ValueError:
      return S_ERROR( "minLifeTime has to be an integer" )
    totalCleaned = 0
    for table in ( "CredDB_OATokens", "CredDB_OAVerifier" ):
      sqlDel = "DELETE FROM `CredDB_OATokens` WHERE TIMESTAMPDIFF( SECOND, UTC_TIMESTAMP(), ExpirationTime ) < %d" % minLifeTime
      result = self._update( sqlDel )
      if not result[ 'OK' ]:
        return result
      totalCleaned += result[ 'Value' ]
    return S_OK( totalCleaned )



