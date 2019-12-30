class DiscoinError(Exception):
    '''
    This is just a base incase we need to add anything here later
    '''
    pass

class InternalServerError(DiscoinError):
    '''
    This error is raised when the API returns a status code of 5**
    '''
    pass

class BadRequest(DiscoinError):
    '''
    This error is raised when the API returns a status code of 4**
    '''
    pass

class InvalidMethod(DiscoinError):
    '''
    This error is raised when the user tries to use an incorrect method with `utils.api_request`
    '''
    pass