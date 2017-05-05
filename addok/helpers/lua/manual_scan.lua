-- There are case where we need to intersect with only common tokens
-- (thinks for example "rue de", which is a very common search when in autocomplete)
-- Redis will be slow, because it needs to loop over the smallest set entirely, which
-- in this case is big (millions of entries).
-- KEYS are the various words of the search (in they key form: w|xxxx)
-- ARGS[1] one is the number of candidates we want to retrieve
local candidates = {}
-- Take the first 500 documents of the first set
local ids = redis.call('ZREVRANGE', KEYS[1], 0, 500)
for i,id in ipairs(ids) do
    local count = 0;
    -- Check if this ids is available in other sets
    for j,key in ipairs(KEYS) do
        if j > 1 then
            -- we used the first key to get the ids, skip it
            -- slice anyone?
            if redis.call('TYPE', key)['ok'] == 'zset' then
                local rank = redis.call('ZRANK', key, id);
                if type(rank) == 'number' then
                    count = count + 1;
                end
            elseif redis.call('SISMEMBER', key, id) == 1 then
                -- Happens with filters which are sets and not zsets
                count = count + 1;
            end
        end
    end
    -- Yay, this id is on all sets, that's a candidate
    if count == (#KEYS - 1) then
        candidates[#candidates + 1] = id;
    end
    -- we have enough candidates
    if #candidates == tonumber(ARGV[1]) then
        break
    end
end

return candidates
