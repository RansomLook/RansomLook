#!/bin/bash

set -e
set -x

../../redis/src/redis-server ./cache.conf
#--loadmodule ../../RedisJSON/target/release/librejson.so
