import pytz
import os
import logging
from datetime import datetime
from .enums import ExchangeType, CurrencyType, OrderType, OrderSubType, Side
from .logging import LOG as log, \
                         STRAT as slog, \
                         DATA as dlog, \
                         RISK as rlog, \
                         EXEC as exlog, \
                         SLIP as sllog, \
                         TXNS as tlog, \
                         MANUAL as mlog, \
                         ERROR as elog

NOPRINT = True


def create_pair(key: str, typ: type, default=None, container=None) -> property:
    def get(self):
        if hasattr(self, '__' + str(key)):
            return getattr(self, '__' + str(key))
        if default is not None and type(default) == typ:
            if container:
                if container == list:
                    return [default]
                else:
                    raise TypeError('Unrecognized container: %s',
                                    str(container))
            return default
        raise TypeError("%s is unset" % key)

    def set(self, val):
        if container:
            if container == list:
                if not isinstance(val, list) or not all(map(
                        lambda x: isinstance(x, typ), val)):
                    raise TypeError("%s attribute must be set to an "
                                    "instance of %s" % (key, typ))
            else:
                raise TypeError('Unrecognized container: %s',
                                str(container))
        else:
            if not isinstance(val, typ) and not type(val) == typ:
                raise TypeError("%s attribute must be set to an instance of %s"
                                % (key, typ))
        setattr(self, '__' + str(key), val)
    return property(get, set)


def config(cls):
    new_cls_dict = {}
    vars = []
    for k, v in cls.__dict__.items():
        if isinstance(v, type):
            v = create_pair(k, v)
            vars.append(k)
        elif isinstance(v, tuple) and \
                isinstance(v[0], type) and \
                isinstance(v[1], v[0]):
            v = create_pair(k, v[0], v[1])
            vars.append(k)
        elif isinstance(v, list) and \
                isinstance(v[0], type):
            v = create_pair(k, v[0], container=list)
            vars.append(k)
        elif isinstance(v, tuple) and \
                isinstance(v[0], list) and \
                isinstance(v[0][0], type) and \
                isinstance(v[1], list) and \
                isinstance(v[1][0], v[0][0]):
            v = create_pair(k, v[0][0], v[1][0], container=list)
            vars.append(k)

        new_cls_dict[k] = v
    new_cls_dict['__repr__'] = __repr__
    new_cls_dict['_vars'] = vars
    new_cls_dict['_excludes'] = []
    return type(cls)(cls.__name__, cls.__bases__, new_cls_dict)


def __init__(self, **kwargs) -> None:
    for item in self._vars:
        if item not in kwargs:
            log.debug('WARNING %s unset!', item)
        else:
            setattr(self, item, kwargs.get(item))

        getattr(self, item)  # make sure all are set.


def __repr__(self) -> str:
    # log.warn(str(self.__class__))
    return '<' + ', '.join([x + '-' + str(getattr(self, x))
                           for x in self._vars if hasattr(self, x) and
                           x not in self._excludes]) + '>'


def struct(cls):
    new_cls_dict = {}

    vars = []
    excludes = []

    if len(cls.__bases__) > 1:
        raise Exception("Structs only support single inheritance")
    for k, v in cls.__dict__.items():
        if isinstance(v, type):
            v = create_pair(k, v)
            vars.append(k)
        elif isinstance(v, tuple) and \
                isinstance(v[0], type) and \
                isinstance(v[1], v[0]):
            if len(v) == 3:
                if v[2] == NOPRINT:
                    excludes.append(k)
            v = create_pair(k, v[0], v[1])
            vars.append(k)
        elif isinstance(v, tuple) and \
                isinstance(v[0], type) and \
                v[1] == NOPRINT:
            if v == bool:
                log.warn('WARNING - bool value ambiguitiy, interpretting '
                         'as PRINT -- If you meant default, '
                         'please be explicit')
            v = create_pair(k, v[0])
            vars.append(k)
            # v = create_pair(k, v[0])

        new_cls_dict[k] = v
    new_cls_dict['__init__'] = __init__
    new_cls_dict['__repr__'] = __repr__
    new_cls_dict['_vars'] = vars
    new_cls_dict['_excludes'] = excludes
    return type(cls)(cls.__name__, cls.__bases__, new_cls_dict)


def parse_date(indate: str) -> datetime:
    try:
        date = datetime.utcfromtimestamp(float(indate))
        date = pytz.utc.localize(date).astimezone(
            pytz.timezone('EST')).replace(tzinfo=None)
    except ValueError:
        date = datetime.strptime(indate, "%Y-%m-%dT%H:%M:%S.%fZ")
    return date


def ex_type_to_ex(ex: ExchangeType):
    if ex == ExchangeType.GDAX:
        from .exchanges.gdax import GDAXExchange
        return GDAXExchange
    elif ex == ExchangeType.GEMINI:
        from .exchanges.gemini import GeminiExchange
        return GeminiExchange
    elif ex == ExchangeType.KRAKEN:
        from .exchanges.kraken import KrakenExchange
        return KrakenExchange
    raise Exception('Exchange type not implemented : %s ' % ex)


def currency_to_string_gdax(cur: CurrencyType) -> str:
    if cur == CurrencyType.BTC:
        return 'BTC-USD'


def order_type_to_string_gdax(typ: OrderType) -> str:
    if typ == OrderType.LIMIT:
        return 'limit'
    elif typ == OrderType.MARKET:
        return 'market'


def trade_req_to_params_gdax(req) -> dict:
    p = {}
    p['price'] = str(req.price)
    p['size'] = str(req.volume)
    p['product_id'] = currency_to_string_gdax(req.currency)
    p['type'] = order_type_to_string_gdax(req.order_type)

    if req.order_sub_type == OrderSubType.FILL_OR_KILL:
        p['time_in_force'] = 'FOK'
    elif req.order_sub_type == OrderSubType.POST_ONLY:
        p['post_only'] = '1'
    return p


def get_keys_from_environment(prefix: str) -> tuple:
    key = os.environ[prefix + '_API_KEY']
    secret = os.environ[prefix + '_API_SECRET']
    passphrase = os.environ[prefix + '_API_PASS']
    return key, secret, passphrase


def str_to_currency_type(s: str) -> CurrencyType:
    s = s.upper()
    if 'BTC' in s:
        return CurrencyType.BTC
    if 'ETH' in s:
        return CurrencyType.ETH
    if 'LTC' in s:
        return CurrencyType.LTC
    return CurrencyType.USD


def str_to_side(s: str) -> Side:
    s = s.upper()
    if 'BUY' in s or 'BID' in s:
        return Side.BUY
    if 'SELL' in s or 'ASK' in s:
        return Side.SELL
    return Side.NONE


def str_to_order_type(s: str) -> OrderType:
    s = s.upper()
    if 'MARKET' in s:
        return OrderType.MARKET
    if 'LIMIT' in s:
        return OrderType.LIMIT
    return OrderType.NONE


def str_to_exchange(exchange: str) -> ExchangeType:
        if 'bitfinex' in exchange:
            return ExchangeType.BITFINEX
        elif 'bitstamp' in exchange:
            return ExchangeType.BITSTAMP
        elif 'gemini' in exchange:
            return ExchangeType.GEMINI
        elif 'hitbtc' in exchange:
            return ExchangeType.HITBTC
        elif 'itbit' in exchange:
            return ExchangeType.ITBIT
        elif 'kraken' in exchange:
            return ExchangeType.KRAKEN
        elif 'lake' in exchange:
            return ExchangeType.LAKE
        else:
            return ExchangeType.GDAX


def exchange_to_file(exchange: ExchangeType) -> str:
    if exchange == ExchangeType.BITSTAMP:
        log.critical('Backtesting against bitstamp data')
        return "./data/exchange/bitstampUSD.csv"
    elif exchange == ExchangeType.BITFINEX:
        log.critical('Backtesting against bitfinex data')
        return "./data/exchange/bitfinexUSD.csv"
    elif exchange == ExchangeType.ITBIT:
        log.critical('Backtesting against itbit data')
        return "./data/exchange/itbitUSD.csv"
    elif exchange == ExchangeType.KRAKEN:
        log.critical('Backtesting against kraken data')
        return "./data/exchange/krakenUSD.csv"
    elif exchange == ExchangeType.HITBTC:
        log.critical('Backtesting against hitbtc data')
        return "./data/exchange/hitbtcUSD.csv"
    elif exchange == ExchangeType.LAKE:
        log.critical('Backtesting against lake data')
        return "./data/exchange/lakeUSD.csv"
    else:
        log.critical('Backtesting against coinbase data')
        return "./data/exchange/coinbaseUSD.csv"


def set_verbose():
    # Print/log extra info
    # olog.propagate = True
    # slog.propagate = True
    # elog.propagate = True
    # dlog.propagate = False  # too much
    # tlog.propagate = True
    # mlog.propagate = True
    log.setLevel(logging.DEBUG)
    slog.setLevel(logging.DEBUG)
    dlog.setLevel(logging.DEBUG)
    rlog.setLevel(logging.DEBUG)
    exlog.setLevel(logging.DEBUG)
    sllog.setLevel(logging.DEBUG)
    tlog.setLevel(logging.DEBUG)
    mlog.setLevel(logging.DEBUG)
    elog.setLevel(logging.DEBUG)
    log.info('running in verbose mode!')
