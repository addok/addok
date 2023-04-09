# Tutorial

This tutorial will cover an installation from scratch of a France dedicated
Addok instance in an Ubuntu server.

You need sudo grants on this server, and it must be connected to Internet.

## Install system dependencies

    sudo apt update
    sudo apt install redis-server python3 python3-dev python-virtualenv build-essential git wget nginx uwsgi uwsgi-plugin-python3 bzip2

Note: any version of python above or equal to 3.7 is OK.

## Create a Unix user

Here we use the name `addok`, but this name is up to you. Remember to change it
on the various commands and configuration files if you go with your own.

    sudo useradd -N addok -m -d /srv/addok/
    sudo chsh -s /bin/bash addok

## Create config folder

    sudo mkdir /etc/addok/
    sudo chown addok /etc/addok

## Login as this new user

    sudo -u addok -i

From now on, until we say differently, the commands are run as `addok` user.


## Create a virtualenv and activate it

    python3.6 -m venv /srv/addok/venv
    source /srv/addok/venv/bin/activate

Note: this activation is not persistent, so if you open a new terminal window,
you will need to run again this last line.

## Upgrade pip and setuptools to latest

    pip install pip setuptools --upgrade

## Install addok and plugins

    pip install addok addok-fr addok-france

Note: if you want batch CSV support on the HTTP API, also install the plugin
`addok-csv`.

Check that the installation is successful so far by running this command:

    addok --help

If you see no error but the list of addok commands, congratulations, you can proceed!

If not, keep courage, try to read the error message, go back through previous steps and
check that everything has been done successfully. And if you are lost, [create an issue the addok
tracker](https://github.com/addok/addok/issues) to ask for help.

## Create a local configuration file

    nano /etc/addok/addok.conf

And paste this configuration:
```
QUERY_PROCESSORS_PYPATHS = [
    "addok.helpers.text.check_query_length",
    "addok_france.extract_address",
    "addok_france.clean_query",
    "addok_france.remove_leading_zeros",
]
SEARCH_RESULT_PROCESSORS_PYPATHS = [
    "addok.helpers.results.match_housenumber",
    "addok_france.make_labels",
    "addok.helpers.results.score_by_importance",
    "addok.helpers.results.score_by_autocomplete_distance",
    "addok.helpers.results.score_by_ngram_distance",
    "addok.helpers.results.score_by_geo_distance",
]
PROCESSORS_PYPATHS = [
    "addok.helpers.text.tokenize",
    "addok.helpers.text.normalize",
    "addok_france.glue_ordinal",
    "addok_france.fold_ordinal",
    "addok_france.flag_housenumber",
    "addok.helpers.text.synonymize",
    "addok_fr.phonemicize",
]
```

Save (ctrl+O) and close (Ctrl+X) the file.


## Download ODbL BAN data and uncompress it:

This is for Seine-Saint-Denis, but choose the area you want from the
[download page](https://adresse.data.gouv.fr/data/ban/adresses/latest/addok/):

    wget https://adresse.data.gouv.fr/data/ban/adresses/latest/addok/adresses-addok-93.ndjson.gz
    gunzip adresses-addok-93.ndjson.gz

## Import the data

Run those two commands:

    addok batch adresses-addok-93.ndjson
    addok ngrams

Let's test that everything is ok. Run the addok shell:

    addok shell

Now, in the Addok shell, simply type the name of a place in the area
you imported, and type "Enter". You should see a list of results.
If you want to list the available commands in the shell, type "?" and
hit "Enter" again.

Take the time to play with the shell to start testing Addok.

When you want to proceed with the tutorial, type `QUIT` in the Addok shell
to close it.


## Configure the HTTP API

If you would want to just test the Addok API, you can simply run this command:

    addok serve

And you can now access it through `http://127.0.0.1:7878/`.
For example, to issue a search, you would call this URL:
[http://127.0.0.1:7878/search/?q=epinay sur seine](http://127.0.0.1:7878/search/?q=epinay sur seine
)

But now let's configure a real HTTP server.

### uWSGI

Create a file named `/srv/addok/uwsgi_params`, with this content
(without making any change on it):

```
uwsgi_param  QUERY_STRING       $query_string;
uwsgi_param  REQUEST_METHOD     $request_method;
uwsgi_param  CONTENT_TYPE       $content_type;
uwsgi_param  CONTENT_LENGTH     $content_length;

uwsgi_param  REQUEST_URI        $request_uri;
uwsgi_param  PATH_INFO          $document_uri;
uwsgi_param  DOCUMENT_ROOT      $document_root;
uwsgi_param  SERVER_PROTOCOL    $server_protocol;
uwsgi_param  REQUEST_SCHEME     $scheme;
uwsgi_param  HTTPS              $https if_not_empty;

uwsgi_param  REMOTE_ADDR        $remote_addr;
uwsgi_param  REMOTE_PORT        $remote_port;
uwsgi_param  SERVER_PORT        $server_port;
uwsgi_param  SERVER_NAME        $server_name;
```

Then create a configuration file for uWSGI:

    nano /srv/addok/uwsgi.ini

And paste this content. Double check paths and user name in case you
have customized some of them during this tutorial. If you followed all the bits of the
tutorial without making any change, you can use it as is:

```
[uwsgi]
uid = addok
gid = users
# Python related settings
# the base directory (full path)
chdir           = /srv/addok/
# Addok's wsgi module
module          = addok.http.wsgi
# the virtualenv (full path)
home            = /srv/addok/venv

# process-related settings
# master
master          = true
# maximum number of worker processes
processes       = 4
# the socket (use the full path to be safe
socket          = /srv/addok/uwsgi.sock
# ... with appropriate permissions - may be needed
chmod-socket    = 666
stats           = /srv/addok/stats.sock
# clear environment on exit
vacuum          = true
plugins         = python3

```

### Nginx

Create a new file:

    nano /srv/addok/nginx.conf

with this content:

```
# the upstream component nginx needs to connect to
upstream addok {
    server unix:///srv/addok/uwsgi.sock;
}

# configuration of the server
server {
    # the port your site will be served on
    listen      80;
    listen   [::]:80;
    listen      443 ssl;
    listen   [::]:443 ssl;
    # the domain name it will serve for
    server_name your-domain.org;
    charset     utf-8;

    # max upload size
    client_max_body_size 5M;   # adjust to taste

    location / {
        uwsgi_pass  addok;
        include     /srv/addok/uwsgi_params;
    }
}
```

Remember to adapt the domain name.

### Activate and restart the services

Now quit the `addok` session, simply type ctrl+D.

You should be logged in as your normal user, which is sudoer.

- Activate the Nginx configuration file:

        sudo ln -s /srv/addok/nginx.conf /etc/nginx/sites-enabled/addok

- Activate the uWSGI configuration file:

        sudo ln -s /srv/addok/uwsgi.ini /etc/uwsgi/apps-enabled/addok.ini

- Restart both services:

        sudo systemctl restart uwsgi nginx


Now you should be able to issue the search with an URL like:

    http://yourdomain.org/search/?q=epinay sur seine


Congratulations!

- - -

## Troubleshooting

- Nginx logs are in /var/log/nginx/:

        sudo tail -f /var/log/nginx/error.log

  or

        sudo tail -f /var/log/nginx/access.log

- uWSGI logs are in /var/log/uwsgi:

        sudo tail -f /var/log/uwsgi/addok.log

- To make sure the environment variable is set in the current shell
  if you changed its location:

        echo $ADDOK_CONFIG_MODULE

- Run `addok shell` and look at the output: addok should print the local
  configuration file his loading (or trying to load…), the loaded plugins, etc.

- To check the configuration of addok it self, run `addok shell` and type `CONFIG`.
  You'll be able to check all the configuration keys and be sure they have the
  expected values.

- If your searches are returning nothing at all or very weird results, it may be that you have
  indexed with a different configuration than the one you are using when searching.
