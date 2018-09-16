-- Order tokens according to their max score in index
-- Mainly used when autocompleting a one word search, so
-- documents with a higher importance come first.
local score = {}
for i,k in ipairs(KEYS) do
    score[k] = tonumber(redis.call('ZREVRANGE', k, 0, 1, 'WITHSCORES')[2] or 0)
end
table.sort( KEYS, function (a, b) return score[a] > score[b] end)
return KEYS
