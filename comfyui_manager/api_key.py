import os
from . import utils, config

class ApiKey:
    """Manages API keys for different platforms."""
    __store: dict[str, str] = {}

    def __init__(self):
        self.__cache_file = os.path.join(config.extension_uri, "private.key")
        if os.path.exists(self.__cache_file):
            self.__store = utils.load_dict_pickle_file(self.__cache_file)

    def init(self, request):
        """Initialize API keys, migrating from user settings if needed."""
        # Try to migrate api key from user setting if cache doesn't exist
        if not os.path.exists(self.__cache_file):
            self.__store = {
                "civitai": utils.get_setting_value(request, "api_key.civitai"),
                "huggingface": utils.get_setting_value(request, "api_key.huggingface"),
            }
            self.__update__()
            # Remove api key from user setting
            utils.set_setting_value(request, "api_key.civitai", None)
            utils.set_setting_value(request, "api_key.huggingface", None)
        
        # Load from cache
        self.__store = utils.load_dict_pickle_file(self.__cache_file)
        
        # Return desensitized keys
        result: dict[str, str] = {}
        for key in self.__store:
            v = self.__store[key]
            if v is not None:
                result[key] = v[:4] + "****" + v[-4:]
        return result

    def get_value(self, key: str):
        """Get an API key value."""
        return self.__store.get(key, None)

    def set_value(self, key: str, value: str):
        """Set an API key value."""
        self.__store[key] = value
        self.__update__()

    def __update__(self):
        """Save API keys to cache file."""
        utils.save_dict_pickle_file(self.__cache_file, self.__store) 