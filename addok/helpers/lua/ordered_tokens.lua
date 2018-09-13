-- Order tokens according to their frequency
table.sort( KEYS, function (a, b) return redis.call('ZCARD', a) > redis.call('ZCARD', b) end)
return KEYS
