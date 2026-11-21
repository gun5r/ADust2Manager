"""Stand-in for the real fmod_toolkit in the packaged program: UnityPy imports it only to convert AudioClips to WAV, which the manager never does,
and the real package carries FMOD's proprietary library, which is not redistributed here."""


def raw_to_wav(*args, **kwargs):
    raise RuntimeError("Audio conversion is not available in the packaged program")
