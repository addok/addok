# Configuring Redis

Configuring Redis can significantly improve Addok.

Generic tips from the official doc [this topic](https://redis.io/topics/admin).

See also the [configuration reference](https://redis.io/topics/config).

On Linux, the default configuration file path is `/etc/redis/redis.conf`.

## Persistence

To be able to stop and start Redis without needing a new import, it's important
to let Redis persist the data on disk.
By default, Redis will persist data every x time or every x changes in the data.
The best thing is to totally disable automatic persistence, and do it by hand
when needed. In fact, only after import we need to persist the data. When
Addok is running, there is not need to persist (addok will create some temporary
keys from time to time, but they are volatile).

To deactivate auto save for the running instance, type:

```
redis-cli config set save ""
```

If you want to do it for good, comment the `save` lines in the redis conf.

This is the perfect setting for running Addok. But remember that the configuration
if for the Redis instance, so if you have other services than Addok using it,
you may configure it your way.

## Import

When importing data, you need to persist it, so a restart of Redis will reload it.

You can either:

- keep the normal redis `save` configuration, which will persist on the fly
  while importing. This will make the import a bit slower, and consume a bit
  more memory during the import.
- issue a `redis-cli bgsave` after the import: this is the faster scenario,
  because Redis will be ready to use just after the import, `bgsave` being
  asynchronous. But this will use more or less the double memory when doing the
  `bgsave`, because Redis will create a subprocess;
- issue a `redis-cli save`, which is synchronous: this will block Redis for one
  or two minutes (depending on the data you imported), but there is no extra
  memory usage


## Security

Before going live, make sure to have a look at
[the security page](https://redis.io/topics/security).
