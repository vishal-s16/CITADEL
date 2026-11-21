"""Custom domain exceptions for user-friendly error reporting."""


class SteganographyError(Exception):
    """Base exception for all steganography application errors."""


class InvalidImageError(SteganographyError):
    """Raised when an uploaded image is invalid, unreadable, or corrupted."""


class UnsupportedImageFormatError(SteganographyError):
    """Raised when the container image format is not supported."""


class UnsupportedFileExtensionError(SteganographyError):
    """Raised when a payload file extension does not match the selected category."""


class EmptyFileSelectionError(SteganographyError):
    """Raised when no payload files are provided for encoding."""


class CapacityExceededError(SteganographyError):
    """Raised when the payload exceeds the container image's storage capacity."""


class CompressionError(SteganographyError):
    """Raised when payload compression or decompression fails."""


class EncryptionError(SteganographyError):
    """Raised when payload encryption fails or parameters are invalid."""


class DecryptionError(SteganographyError):
    """Raised when decryption fails due to wrong password or corrupted data."""


class PasswordRequiredError(SteganographyError):
    """Raised when an encrypted payload is extracted without providing a password."""


class NoPayloadError(SteganographyError):
    """Raised when no payload from this application is detected in the image."""


class CorruptedPayloadError(SteganographyError):
    """Raised when payload headers, structure, or integrity checks fail."""
