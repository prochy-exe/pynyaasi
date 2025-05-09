import threading
from functools import lru_cache
from typing import Callable

import requests, random

BACKEND_FACTORY_T = Callable[[], requests.Session]
_GLOBAL_BACKEND_FACTORY: BACKEND_FACTORY_T = requests.session

def generate_user_agent():
    """
    Generate a random user agent string.

    Returns:
        str: A user agent string that mimics a user agent of a browser on a desktop device.
    """
    os_list = ['Windows NT 10.0', 'Windows NT 7.0', 'Macintosh', 'Linux x86_64']
    browser_list = ['Chrome', 'Firefox', 'Safari', 'Edge']

    os = random.choice(os_list)
    browser = random.choice(browser_list)
    device = 'Desktop'

    if browser == 'Chrome':
        browser_version = f'{random.randint(70, 90)}.{random.randint(0, 9)}.{random.randint(1000, 9999)}.{random.randint(0, 99)}'
    elif browser == 'Firefox':
        browser_version = f'{random.randint(60, 80)}.{random.randint(0, 9)}'
    elif browser == 'Safari':
        browser_version = f'{random.randint(10, 14)}.{random.randint(0, 9)}'
    elif browser == 'Edge':
        browser_version = f'{random.randint(15, 20)}.{random.randint(1000, 9999)}.{random.randint(0, 99)}'

    user_agent = f'Mozilla/5.0 ({os}; {device}) AppleWebKit/537.36 (KHTML, like Gecko) {browser}/{browser_version}'

    return user_agent

def configure_http_backend(backend_factory: BACKEND_FACTORY_T = requests.Session) -> None:
    """
    Configure the HTTP backend by providing a `backend_factory`. Any HTTP calls made by `huggingface_hub` will use a
    Session object instantiated by this factory. This can be useful if you are running your scripts in a specific
    environment requiring custom configuration (e.g. custom proxy or certifications).

    Use [`get_session`] to get a configured Session. Since `requests.Session` is not guaranteed to be thread-safe,
    `huggingface_hub` creates 1 Session instance per thread. They are all instantiated using the same `backend_factory`
    set in [`configure_http_backend`]. A LRU cache is used to cache the created sessions (and connections) between
    calls. Max size is 128 to avoid memory leaks if thousands of threads are spawned.

    See [this issue](https://github.com/psf/requests/issues/2766) to know more about thread-safety in `requests`.

    Example:
    ```py
    import requests
    from huggingface_hub import configure_http_backend, get_session

    # Create a factory function that returns a Session with configured proxies
    def backend_factory() -> requests.Session:
        session = requests.Session()
        session.proxies = {"http": "http://10.10.1.10:3128", "https": "https://10.10.1.11:1080"}
        return session

    # Set it as the default session factory
    configure_http_backend(backend_factory=backend_factory)

    # In practice, this is mostly done internally in `huggingface_hub`
    session = get_session()
    ```
    """
    global _GLOBAL_BACKEND_FACTORY
    _GLOBAL_BACKEND_FACTORY = backend_factory
    _get_session_from_cache.cache_clear()


def get_session() -> requests.Session:
    """
    Get a `requests.Session` object, using the session factory from the user.

    Use [`get_session`] to get a configured Session. Since `requests.Session` is not guaranteed to be thread-safe,
    `huggingface_hub` creates 1 Session instance per thread. They are all instantiated using the same `backend_factory`
    set in [`configure_http_backend`]. A LRU cache is used to cache the created sessions (and connections) between
    calls. Max size is 128 to avoid memory leaks if thousands of threads are spawned.

    See [this issue](https://github.com/psf/requests/issues/2766) to know more about thread-safety in `requests`.

    Example:
    ```py
    import requests
    from huggingface_hub import configure_http_backend, get_session

    # Create a factory function that returns a Session with configured proxies
    def backend_factory() -> requests.Session:
        session = requests.Session()
        session.proxies = {"http": "http://10.10.1.10:3128", "https": "https://10.10.1.11:1080"}
        return session

    # Set it as the default session factory
    configure_http_backend(backend_factory=backend_factory)

    # In practice, this is mostly done internally in `huggingface_hub`
    session = get_session()
    ```
    """
    cached_session = _get_session_from_cache(thread_ident=threading.get_ident())
    cached_session.headers['User-Agent'] = generate_user_agent()
    return cached_session


@lru_cache(maxsize=128)  # default value for Python>=3.8. Let's keep the same for Python3.7
def _get_session_from_cache(thread_ident: int) -> requests.Session:
    """
    Create a new session per thread using global factory. Using LRU cache (maxsize 128) to avoid memory leaks when
    using thousands of threads. Cache is cleared when `configure_http_backend` is called.
    """
    _ = thread_ident
    return _GLOBAL_BACKEND_FACTORY()
