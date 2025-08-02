__title__ = "BDDS (automated testing framework)"
__author__ = "Clive Bostock"
__date__ = "2024-06-22"
__doc__ = """The framework_errors module, defines the exceptions provided for the BDDS framework."""


#
# Custom exceptions classes should be placed in this file, which should be imported to access the custom exceptions.
#
class UnsupportedPlatform(Exception):
    """A custom exception to deal with unsupported/unrecognised platforms."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


class BehaveStepFailed(Exception):
    """A custom exception to signal a behave step failure."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


class UnresolvedIdentityManagement(Exception):
    """A custom exception to deal with unresolved identity management service."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


class InjectAnchorsFailure(Exception):
    """A custom exception to deal with failure reported by injectAnchors.js"""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


class CredentialsNotEstablished(Exception):
    """This exception is expected where the secrets.ini, credential_source entry is set to "local", and also the
    password is not established in the credentials section of the secrets.ini file. If the credential_source entry is
    not established, use the '-D user_password=<password>' option when running the behave command. You should only to
    run this once, or whenever the password has been updated."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


class APIOutOfSequence(Exception):
    """This exception is raised when an API has been called at the wrong stage of a number of steps."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


class SystemCommandError(Exception):
    """This exception is raised when we detect a failure when attempting to execute an operating system command, or
    bash shell script, via a Python system() call."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


class UnsupportedOption(Exception):
    """This exception is raised when an options parameter value is passed to a function or method, which is interpreted
    as an unsupported option (an unrecognised value)."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


class InvalidSelection(Exception):
    """This exception is raised when an API receives a selection (e.g. a match string of some sort) and the match
    fails or is deemed not valid."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


class InvalidParameter(Exception):
    """This exception is raised when an invalid parameter is passed to a program."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


class ValueUnmatched(Exception):
    """This exception is raised when an attempt is made to select a value from a PopupLOV or SelectList, which has no
    match."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


class LovIndexUnmatched(Exception):
    """This exception is raised when an attempt is made to select a value by index, and which is out of range,
    from a PopupLOV or SelectList."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


class PartValueUnmatched(Exception):
    """This exception is raised when an attempt is made to select a value, by partial match, from a PopupLOV or
    SelectList, which has no match."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


class UnrecognisedElement(Exception):
    """This exception is raised when a class method, does not recognise a passed element in some way.
    For example, it may expect a specific attribute which is not found to be there."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


class PLSQLScriptError(Exception):
    """This exception is raised when the DBSession.run_plsql_block method detects an error from the b_status
    bind parameter."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)
