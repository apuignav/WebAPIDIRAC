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
                                                    'Type' : 'ENUM ("%s") NOT NULL' % '","'.join( self.VALID_OAUTH_TOKEN_TYPES ),
                                                },
                                      'PrimaryKey' : 'Token',
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
                                                      'ExpirationTime' : 'DATETIME'
                                                  },
                                      'PrimaryKey' : 'Verifier',
                                     }

    return self._createTables( tablesD )


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

  def generateToken( self, userDN, userGroup, consumerKey, tokenType = "request", lifeTime = 86400 ):
    result = self.getIdentityId( userDN, userGroup )
    if not result[ 'OK' ]:
      self.logger.error( result[ 'Value' ] )
      return result
    userId = result[ 'Value' ]
    try:
      lifeTime = int( lifeTime )
    except ValueError:
      return S_ERROR( "Life time has to be a positive integer" )
    if lifeTime < 0:
      return S_ERROR( "Life time has to be a positive integer" )
    return self.__generateToken( userId, consumerKey, tokenType, lifeTime )


  def __generateToken( self, userId, consumerKey, tokenType, lifeTime, retries = 5 ):
    tokenType = tokenType.lower()
    if tokenType not in self.VALID_OAUTH_TOKEN_TYPES:
      return S_ERROR( "Invalid token type" )
    sqlType = '"%s"' % tokenType
    token = md5.md5( "%s|%s|%s|%s|%s" % ( userId, type, consumerKey, time.time(), random.random() ) ).hexdigest()
    secret = md5.md5( "%s|%s|%s\%s" % ( userId, consumerKey, time.time(), random.random() ) ).hexdigest()
    if len( consumerKey ) > 64 or len( consumerKey ) < 5:
      return S_ERROR( "Consumer key doesn't have a correct size" )
    result = self._escapeString( consumerKey )
    if not result[ 'OK' ]:
      return result
    sqlConsumerKey = result[ 'Value' ]

    sqlFields = "( Token, Secret, ConsumerKey, UserId, ExpirationTime, Type )"
    sqlValues = [ "'%s'" % token, "'%s'" % secret, sqlConsumerKey, "%d" % userId,
                 "TIMESTAMPADD( SECOND, %d, UTC_TIMESTAMP() )" % lifeTime, sqlType ]
    sqlIn = "INSERT INTO `CredDB_OATokens` %s VALUES ( %s )" % ( sqlFields, ",".join( sqlValues ) )
    result = self._update( sqlIn )
    if not result[ 'OK' ]:
      if result[ 'Message' ].find( "Duplicate key" ) > -1 and retries > 0 :
        return self.__generateToken( userId, consumerKey, tokenType, lifeTime, retries - 1 )
      return result
    return S_OK( ( token, secret ) )

  def getSecret( self, userDN, userGroup, consumerKey, token, tokenType = "request" ):
    result = self.getIdentityId( userDN, userGroup )
    if not result[ 'OK' ]:
      self.logger.error( result[ 'Value' ] )
      return result
    userId = result[ 'Value' ]

    tokenType = tokenType.lower()
    if tokenType not in self.VALID_OAUTH_TOKEN_TYPES:
      return S_ERROR( "Invalid token type" )
    sqlType = '"%s"' % tokenType

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

    sqlCond = [ "UserId = %d" % userId ]
    sqlCond.append( "Token=%s" % sqlToken )
    sqlCond.append( "Type=%s" % sqlType )
    sqlCond.append( "ConsumerKey=%s" % sqlConsumerKey )
    sqlCond.append( "TIMESTAMPDIFF( SECOND, UTC_TIMESTAMP(), ExpirationTime ) > 0" )
    sqlSel = "SELECT Secret FROM `CredDB_OATokens` WHERE %s" % " AND ".join( sqlCond )
    result = self._query( sqlSel )
    if not result[ 'OK' ]:
      return result
    data = result[ 'Value' ]
    if len( data ) and len( data[0] ):
      return S_OK( data[0][0] )
    return S_ERROR( "Token is either unknown or invalid" )

  def getTokens( self, condDict = {} ):
    sqlTables = [ '`CredDB_OATokens` t', '`CredDB_Identities` i' ]
    sqlCond = [ "t.UserId = i.Id"]

    fields = [ 'Token', 'Secret', 'ConsumerKey', 'Type', 'UserDN', 'UserGroup' ]
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

  def generateVerifier( self, userDN, userGroup, consumerKey, lifeTime = 3600, retries = 5 ):
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

    sqlFields = "( Verifier, UserId, ConsumerKey, ExpirationTime )"
    sqlValues = [ "'%s'" % verifier, "%d" % userId, sqlConsumerKey,
                 "TIMESTAMPADD( SECOND, %d, UTC_TIMESTAMP() )" % lifeTime ]
    sqlIn = "INSERT INTO `CredDB_OAVerifier` %s VALUES ( %s )" % ( sqlFields, ",".join( sqlValues ) )
    result = self._update( sqlIn )
    if not result[ 'OK' ]:
      if result[ 'Message' ].find( "Duplicate key" ) > -1 and retries > 0 :
        return self.generateVerifier( userDN, userGroup, consumerKey, lifeTime, retries - 1 )
      return result
    return S_OK( verifier )

  def validateVerifier( self, userDN, userGroup, consumerKey, verifier ):
    result = self.getIdentityId( userDN, userGroup )
    if not result[ 'OK' ]:
      self.logger.error( result[ 'Value' ] )
      return result
    userId = result[ 'Value' ]
    sqlCond = [ "TIMESTAMPDIFF( SECOND, UTC_TIMESTAMP(), ExpirationTime ) > 0" ]
    sqlCond.append( "UserId=%d" % userId )
    if len( consumerKey ) > 64 or len( consumerKey ) < 5:
      return S_ERROR( "Consumer key doesn't have a correct size" )
    result = self._escapeString( consumerKey )
    if not result[ 'OK' ]:
      return result
    sqlConsumerKey = result[ 'Value' ]
    sqlCond.append( "ConsumerKey=%s" % sqlConsumerKey )
    result = self._escapeString( verifier )
    if not result[ 'OK' ]:
      return result
    sqlVerifier = result[ 'Value' ]
    sqlCond.append( "Verifier=%s" % sqlVerifier )
    sqlDel = "DELETE FROM `CredDB_OAVerifier` WHERE %s" % " AND ".join( sqlCond )
    result = self._update( sqlDel )
    if not result[ 'OK' ]:
      return result
    if result[ 'Value' ] < 1:
      return S_ERROR( "Verifier is unknown" )
    return S_OK()



def testDB():
  credDB = CredentialsDB()
  userDN = "/me"
  userGroup = "mygroup"
  consumerKey = "ASDAS"
  print credDB.getIdentityId( userDN, userGroup )
  print credDB.getIdentityId( userDN, userGroup )
  for tType in credDB.VALID_OAUTH_TOKEN_TYPES:
    print "Trying token type: %s" % tType
    result = credDB.generateToken( userDN, userGroup, consumerKey, tokenType = tType )
    if not result[ 'OK' ]:
      print "[ERR] %s" % result['Message']
      sys.exit( 1 )
    tokenPair = result[ 'Value' ]
    result = credDB.getSecret( userDN, userGroup, consumerKey, tokenPair[0], tokenType = tType )
    if not result[ 'OK' ]:
      print "[ERR] %s" % result['Message']
      sys.exit( 1 )
    secret = result[ 'Value' ]
    if secret != tokenPair[1]:
      print "[ERR] SECRET IS DIFFERENT!!"
    print "Token is OK. Revoking token with wrong user..."
    result = credDB.revokeUserToken( "no", "no", tokenPair[0] )
    if not result[ 'OK' ]:
      print "[ERR] %s" % result['Message']
      sys.exit( 1 )
    if result[ 'Value' ] != 0:
      print "[ERR] %d tokens were revoked" % result[ 'Value' ]
      sys.exit( 1 )
    print "Revoking token with user"
    result = credDB.revokeUserToken( userDN, userGroup, tokenPair[0] )
    if not result[ 'OK' ]:
      print "[ERR] %s" % result['Message']
      sys.exit( 1 )
    if result[ 'Value' ] != 1:
      print "[ERR] %d tokens were revoked" % result[ 'Value' ]
      sys.exit( 1 )
    print "Token was revoked"
  print "Cleaning expired tokens"
  result = credDB.cleanExpired()
  if not result[ 'OK' ]:
    print "[ERR] %s" % result['Message']
    sys.exit( 1 )
  print "Generating 1 sec lifetime token"
  result = credDB.generateToken( userDN, userGroup, consumerKey, tokenType = tType, lifeTime = 1 )
  if not result[ 'OK' ]:
    print "[ERR] %s" % result['Message']
    sys.exit( 1 )
  print "Sleeping 2 sec"
  time.sleep( 2 )
  print "Cleaning expired tokens"
  result = credDB.cleanExpired()
  if not result[ 'OK' ]:
    print "[ERR] %s" % result['Message']
    sys.exit( 1 )
  if result[ 'Value' ] < 1:
    print "[ERR] No tokens were cleaned"
    sys.exit( 1 )
  print "%s tokens were cleaned" % result[ 'Value' ]
  print "Generating tokens"
  for tType in credDB.VALID_OAUTH_TOKEN_TYPES:
    print "Trying token type: %s" % tType
    result = credDB.generateToken( userDN, userGroup, consumerKey, tokenType = tType, lifeTime = 3 )
    if not result[ 'OK' ]:
      print "[ERR] %s" % result['Message']
      sys.exit( 1 )
  print "Retrieving tokens"
  print credDB.getTokens()
  print "Requesting verifier"
  result = credDB.generateVerifier( userDN, userGroup, consumerKey )
  if not result[ 'OK' ]:
    print "[ERR] %s" % result['Message']
    sys.exit( 1 )
  verifier = result[ 'Value' ]
  print "Trying to validate with different consumer"
  result = credDB.validateVerifier( userDN, userGroup, "ASD%s" % consumerKey, verifier )
  if not result[ 'OK' ]:
    print "Not validated with: %s" % result[ 'Message' ]
  else:
    print "[ERR] Validated invalid verifier"
    sys.exit( 1 )
  print "Validating it"
  result = credDB.validateVerifier( userDN, userGroup, consumerKey, verifier )
  if not result[ 'OK' ]:
    print "[ERR] %s" % result['Message']
    sys.exit( 1 )
  print "ALL OK"

if __name__ == "__main__":
  testDB()
