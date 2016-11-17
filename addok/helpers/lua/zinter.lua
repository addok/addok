-- Like a sinter, but on sorted set.
-- Args are:
-- - unique name to be used for tmp key (we don't pass it has key
--   to make the API simpler, and because it's tmp, so no cluster issue)
-- - the number of items to retrieve
redis.call('ZINTERSTORE', ARGV[1], #KEYS, unpack(KEYS))
-- `stop` is inclusive, so we do minus one to keep the signature human ready
-- i.e. if I want two elements, I just pass "2", not "1".
local ids = redis.call('ZREVRANGE', ARGV[1], 0, tonumber(ARGV[2]) - 1)
redis.call('DEL', ARGV[1])
return ids
