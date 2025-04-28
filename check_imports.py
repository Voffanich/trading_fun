try:
    from binance.client import Client
    print("python-binance - OK")
except ImportError as e:
    print(f"python-binance - ERROR: {e}")

try:
    import binance.connector
    print("binance.connector - OK")
except ImportError as e:
    print(f"binance.connector - ERROR: {e}")

try:
    from binance.um_futures import UMFutures
    print("binance.um_futures - OK")
except ImportError as e:
    print(f"binance.um_futures - ERROR: {e}")

try:
    import pandas
    print("pandas - OK")
except ImportError as e:
    print(f"pandas - ERROR: {e}")

try:
    import numpy
    print("numpy - OK")
except ImportError as e:
    print(f"numpy - ERROR: {e}")

try:
    import matplotlib
    print("matplotlib - OK")
except ImportError as e:
    print(f"matplotlib - ERROR: {e}")

try:
    import requests
    print("requests - OK")
except ImportError as e:
    print(f"requests - ERROR: {e}") 