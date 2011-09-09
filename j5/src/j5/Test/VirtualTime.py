#!/usr/bin/env python

"""Implements a system for simulating a virtual time (based on an offset from the current actual time) so that all Python objects believe it though the actual system time remains the same"""

# TODO: see to what extent it is possible to only patch the functions when a virtual time is in place...

import sys
import threading
import types
import time
import datetime as datetime_module

_original_time = time.time
_original_asctime = time.asctime
_original_ctime = time.ctime
_original_gmtime = time.gmtime
_original_localtime = time.localtime
_original_strftime = time.strftime
_original_sleep = time.sleep

_virtual_time_state = threading.Condition()
_time_offset = 0

def _virtual_time():
    """Overlayed form of time.time() that adds _time_offset"""
    return _original_time() + _time_offset

def _virtual_asctime(when_tuple=None):
    """Overlayed form of time.asctime() that adds _time_offset"""
    return _original_asctime(_virtual_localtime() if when_tuple is None else when_tuple)

def _virtual_ctime(when=None):
    """Overlayed form of time.ctime() that adds _time_offset"""
    return _original_ctime(_virtual_time() if when is None else when)

def _virtual_gmtime(when=None):
    """Overlayed form of time.gmtime() that adds _time_offset"""
    return _original_gmtime(_virtual_time() if when is None else when)

def _virtual_localtime(when=None):
    """Overlayed form of time.localtime() that adds _time_offset"""
    return _original_localtime(_virtual_time() if when is None else when)

def _virtual_strftime(format, when_tuple=None):
    """Overlayed form of time.strftime() that adds _time_offset"""
    return _original_strftime(format, _virtual_localtime() if when_tuple is None else when_tuple)

def _virtual_sleep(seconds):
    """Overlayed form of time.sleep() that responds to changes to the virtual time"""
    expected_end = _virtual_time() + seconds
    while True:
        remaining = expected_end - _virtual_time()
        if remaining <= 0:
            break
        # At least limit the fallout to a reasonably busy wait to get the lock
        if _virtual_time_state.acquire(False):
            try:
                remaining = expected_end - _virtual_time()
                _virtual_time_state.wait(remaining)
            finally:
                _virtual_time_state.release()
        else:
            _original_sleep(0.001)

time.time = _virtual_time
time.asctime = _virtual_asctime
time.ctime = _virtual_ctime
time.gmtime = _virtual_gmtime
time.localtime = _virtual_localtime
time.strftime = _virtual_strftime
time.sleep = _virtual_sleep

_original_datetime_module = datetime_module
_original_datetime_type = _original_datetime_module.datetime
_original_datetime_now = _original_datetime_type.now
_original_datetime_utcnow = _original_datetime_type.utcnow

_virtual_datetime_attrs = dict(_original_datetime_type.__dict__.items())
class datetime(_original_datetime_module.datetime):
    def __new__(cls, *args, **kwargs):
        dt = super(_virtual_datetime_type, cls).__new__(cls, *args, **kwargs)
        newargs = list(dt.timetuple()[0:6])+[dt.microsecond, dt.tzinfo]
        return _original_datetime_type.__new__(cls, *newargs)

    @classmethod
    def now(cls):
        """Virtualized datetime.datetime.now()"""
        dt = super(_virtual_datetime_type, cls).now() + _original_datetime_module.timedelta(seconds=_time_offset)
        newargs = list(dt.timetuple()[0:6])+[dt.microsecond, dt.tzinfo]
        return _original_datetime_type.__new__(cls, *newargs)

    @classmethod
    def utcnow(cls):
        """Virtualized datetime.datetime.utcnow()"""
        dt = super(_virtual_datetime_type, cls).utcnow() + _original_datetime_module.timedelta(seconds=_time_offset)
        newargs = list(dt.timetuple()[0:6])+[dt.microsecond, dt.tzinfo]
        return _original_datetime_type.__new__(cls, *newargs)

_virtual_datetime_type = datetime
_original_datetime_module.datetime = _virtual_datetime_type

def local_datetime_to_time(dt):
    """converts a naive datetime object to a local time float"""
    return time.mktime(dt.timetuple()) + dt.microsecond * 0.000001

def utc_datetime_to_time(dt):
    """converts a naive utc datetime object to a local time float"""
    return time.mktime(dt.utctimetuple()) + dt.microsecond * 0.000001 - (time.altzone if time.daylight else time.timezone)

def set_time(new_time):
    """Sets the current time to the given time.time()-equivalent value"""
    global _time_offset
    _virtual_time_state.acquire()
    try:
        _time_offset = new_time - _original_time()
        _virtual_time_state.notify_all()
    finally:
        _virtual_time_state.release()

def restore_time():
    """Reverts to real time operation"""
    global _time_offset
    _virtual_time_state.acquire()
    try:
        _time_offset = 0
        _virtual_time_state.notify_all()
    finally:
        _virtual_time_state.release()

def set_local_datetime(dt):
    """Sets the current time using the given naive local datetime object"""
    set_time(local_datetime_to_time(dt))

def set_utc_datetime(dt):
    """Sets the current time using the given naive utc datetime object"""
    set_time(utc_datetime_to_time(dt))

