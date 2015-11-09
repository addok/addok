"""Import from PostgreSQL database."""

import psycopg2
import psycopg2.extras

from addok import config


connection = psycopg2.connect(**config.PSQL)


def query(*args):
    extrawhere = config.PSQL_EXTRAWHERE
    limit = ''
    if config.PSQL_LIMIT:
        print('Adding limit', config.PSQL_LIMIT)
        limit = 'LIMIT {limit}'.format(limit=config.PSQL_LIMIT)
    # We use python format because SQL one doesn't handle empty strings.
    sql = config.PSQL_QUERY.format(extrawhere=extrawhere, limit=limit)
    cur = connection.cursor("addok", cursor_factory=psycopg2.extras.DictCursor)
    cur.itersize = config.PSQL_ITERSIZE
    cur.execute(sql)
    print('Query executed with itersize', cur.itersize)

    for row in cur.__iter__():
        yield dict(row)
    cur.close()
