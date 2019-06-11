from cryptography.fernet import Fernet

_KEY = None

def _generate_key():
    return Fernet.generate_key()

def _crypt_pwd(clear_text):
    if _KEY is not None and type(clear_text) in [str]:
        # encrypt
        cipher_suite = Fernet(_KEY)
        ciphered_text = cipher_suite.encrypt(clear_text)  #required to be bytes
        return ciphered_text
    else:
        print('No key')
        return None

def _decrypt_pwd(ciphered_text):
    if _KEY is not None and type(ciphered_text) in [str]:
        cipher_suite = Fernet(_KEY)
        crypted_text = ciphered_text  #required to be bytes
        clear_text = (cipher_suite.decrypt(crypted_text))
        return clear_text
    else:
        print('No key')
        return None

if __name__ == '__main__':
    _KEY = _generate_key()
    print _KEY

    pwd = "superpassword"
    t = _crypt_pwd(pwd)
    print t

    mak = "gAAAAABc9sUxGOotVoGbUMy4JOtT04d2glBu-9TRNtgUcEvReCclCC9wg07_jCfh-9c2rly1zh6FD2haDy0gISl8AR0OyRbXOw=="
    c = _decrypt_pwd(mak)
    print c

    print '***** END *****'