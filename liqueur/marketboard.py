import math

from datetime import datetime
from .codes import err_codes, candlestick_type, candlestick_output_type, candlestick_trade_session, subscribe_type
from .structure import Tick, Candlestick, Trade, Quotation
from .applog import AppLog

log = AppLog.get('marketboard')


class MarketBoard():
    app = None
    _cfg = None

    def __init__(self, app, cfg):
        self.app = app
        self._cfg = cfg

    def __del__(self):
        pass

    def subscribe(self, orderbooks):
        for t, val in orderbooks.items():
            if t == subscribe_type.tick:
                if isinstance(val, list):
                    for v in val:
                        (pg, err) = self.app.subscribe_tick(-1, v)
                        self.app.corelog(err)
                else:
                    (pg, err) = self.app.subscribe_tick(-1, val)
                    self.app.corelog(err)
            elif t == subscribe_type.candlestick:
                for oid, typ in val.items():
                    self.app.corelog(
                        self.app.subscribe_candlestick(
                            oid, candlestick_type[typ],
                            candlestick_output_type.new,
                            candlestick_trade_session.daylight))

    def OnNotifyServerTime(self, sHour, sMinute, sSecond, nTotal):
        dt = datetime.combine(datetime.now(), datetime.strptime(
            (('%d:%d:%d') % (sHour, sMinute, sSecond)), '%H:%M:%S').time())
        log.info(dt)
        self.app.send_heartbeat(dt)
        # market event

    def OnConnection(self, nKind, nCode):
        if self.app.corelog(nCode):
            self.stop()
            return

        if nKind == err_codes.subject_connection_connected:
            log.info('Session...established')
        elif nKind == err_codes.subject_connection_disconnect:
            log.warning('Session...disconnect')
            self.app.stop()
        elif nKind == err_codes.subject_connection_stocks_ready:
            log.info('Session...ready')
            self.app.send_heartbeat()
            self.subscribe(self._cfg.subscription)
        elif nKind == err_codes.subject_connection_fail:
            log.error('Connection failure')
            self.app.stop()
        else:
            self.app.corelog(nKind)

    def _on_notify_tick(
            self, sMarketNo, sIndex, nPtr, nDate, nTimehms, nTimemillismicros, nBid, nAsk, nClose, nQty, nSimulate):
        (p_stock, err) = self.app.get_profile(sMarketNo, sIndex)
        if self.app.corelog(err):
            return

        _year = int(nDate / 10000)
        nDate %= 10000
        _mon = int(nDate / 100)
        _day = nDate % 100
        _hour = int(nTimehms / 10000)
        nTimehms %= 10000
        _min = int(nTimehms / 100)
        _sec = nTimehms % 100
        dt = datetime(_year, _mon, _day, _hour, _min, _sec, nTimemillismicros)

        orderbook_id = p_stock.bstrStockNo
        orderbook_code = p_stock.bstrStockName
        cardinal_num = math.pow(10, p_stock.sDecimal)
        bid = float(nBid / cardinal_num)
        ask = float(nAsk / cardinal_num)
        close = float(nClose / cardinal_num)

        tick = Tick(orderbook_id, dt, orderbook_code, bid, ask, close, nQty, nSimulate)
        self.app.on_quote(tick)

    def OnNotifyTicks(
            self, sMarketNo, sIndex, nPtr, nDate, nTimehms, nTimemillismicros, nBid, nAsk, nClose, nQty, nSimulate):
        return self._on_notify_tick(
            sMarketNo, sIndex, nPtr, nDate, nTimehms, nTimemillismicros, nBid, nAsk, nClose, nQty, nSimulate)

    def OnNotifyHistoryTicks(
            self, sMarketNo, sIndex, nPtr, nDate, nTimehms, nTimemillismicros, nBid, nAsk, nClose, nQty, nSimulate):
        return self._on_notify_tick(
            sMarketNo, sIndex, nPtr, nDate, nTimehms, nTimemillismicros, nBid, nAsk, nClose, nQty, nSimulate)

    def OnNotifyKLineData(self, bstrStockNo, bstrData):
        if bstrData[:len('1989/00/14')] == '1989/00/14':
            return

        [time_string, open_price, high_price, low_price, close_price, qty] = bstrData.split(',')
        if len(time_string) > 10:
            dt = datetime.strptime(time_string, '%Y/%m/%d %H:%M')
        else:
            dt = datetime.strptime(time_string, '%Y/%m/%d')

        candlestick = Candlestick(bstrStockNo, dt, open_price, high_price, low_price, close_price, qty)
        self.app.on_quote(candlestick)

    def OnNotifyStockList(self, sMarketNo, bstrStockData):
        stock_list = []
        for stock_category in bstrStockData.split('\n'):
            for stock_info in stock_category.split(';'):
                s = stock_info.split(',')
                stock_list.append(s[0])
        self.app.on_quote(stock_list)

    def OnNotifyBest5(self, sMarketNo, sStockidx, nBestBid1, nBestBidQty1, nBestBid2, nBestBidQty2, nBestBid3,
                      nBestBidQty3, nBestBid4, nBestBidQty4, nBestBid5, nBestBidQty5, nExtendBid, nExtendBidQty,
                      nBestAsk1, nBestAskQty1, nBestAsk2, nBestAskQty2, nBestAsk3, nBestAskQty3, nBestAsk4,
                      nBestAskQty4, nBestAsk5, nBestAskQty5, nExtendAsk, nExtendAskQty, nSimulate):
        (p_stock, err) = self.app.get_profile(sMarketNo, sStockidx)
        if self.app.corelog(err):
            return

        quotation = Quotation(
            p_stock.bstrStockNo, datetime.now(),
            [Trade(nBestBid1, nBestBidQty1),
             Trade(nBestBid2, nBestBidQty2),
             Trade(nBestBid3, nBestBidQty3),
             Trade(nBestBid4, nBestBidQty4),
             Trade(nBestBid5, nBestBidQty5)],
            [Trade(nBestAsk1, nBestAskQty1),
             Trade(nBestAsk2, nBestAskQty2),
             Trade(nBestAsk3, nBestAskQty3),
             Trade(nBestAsk4, nBestAskQty4),
             Trade(nBestAsk5, nBestAskQty5)])
        self.app.on_quote(quotation)