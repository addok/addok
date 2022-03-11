-- Order tokens according to their frequency
local frequency = {}
for i,k in ipairs(KEYS) do
    frequency[k] = redis.call('ZCARD', k)
end
table.sort( KEYS, function (a, b) return frequency[a] > frequency[b] end)
return KEYS
