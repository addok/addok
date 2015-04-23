from fabric.api import task, env, roles, cd, hide, sudo, execute, puts


env.project_name = 'addok'
env.repository = 'https://github.com/etalab/addok.git'
env.local_branch = 'master'
env.remote_ref = 'origin/master'
env.requirements_file = 'requirements.txt'
env.use_ssh_config = True
env.shell = "/bin/bash -c"  # Default uses -l option that we don't want.
env.virtualenv_dir = '/home/addok/.virtualenvs/addok'
env.project_dir = '/home/addok/src/'
env.restart_command = 'sudo service addok restart'


def run_as_addok(*args, **kwargs):
    """
    Run command sudoing user `addok`.
    """
    kwargs['user'] = "addok"
    return sudo(*args, **kwargs)


# =============================================================================
# Tasks which set up deployment environments
# =============================================================================

@task
def dev():
    """
    Use the dev deployment environment on Etalab servers.
    You need the "banapidev" server to be referenced in your ~/.ssh/config
    file.
    """
    server = 'banapidev'
    env.roledefs = {
        'web': [server],
    }
    env.system_users = {server: 'addok'}


@task
def live():
    """
    Use the live deployment environment on Etalab servers.
    You need the "banapi" server to be referenced in your ~/.ssh/config file.
    """
    server = 'banapi'
    env.roledefs = {
        'web': [server],
    }
    env.system_users = {server: 'addok'}


# Set the default environment.
dev()


# =============================================================================
# Actual tasks
# =============================================================================

@task
@roles('web')
def setup():
    """
    Install the service (tested on Ubuntu 14.04).
    """
    sudo('apt install redis-server python3.4-dev python-virtualenv python-pip '
         'virtualenvwrapper')
    # run_as_addok('source /usr/local/bin/virtualenvwrapper.sh')
    run_as_addok('mkvirtualenv addok --python=/usr/bin/python3.4')
    run_as_addok('git clone {repository} {project_dir}'.format(**env))
    with cd(env.project_dir):
        run_as_addok('pip install -r {requirements_file}'.format(**env))


@task
@roles('web')
def restart():
    """
    Restart the web service.
    """
    run_as_addok(env.restart_command)


@task
@roles('web')
def update(action='check'):
    """
    Update the repository (server-side).
    """
    with cd(env.project_dir):
        remote, dest_branch = env.remote_ref.split('/', 1)
        run_as_addok('git fetch {remote}'.format(
            remote=remote, dest_branch=dest_branch, **env))
        with hide('running', 'stdout'):
            cmd = 'git diff-index --cached --name-only {remote_ref}'
            changed_files = run_as_addok(cmd.format(**env)).splitlines()
        if not changed_files and action != 'force':
            # No changes, we can exit now.
            return
        run_as_addok('git merge {remote_ref}'.format(**env))
        run_as_addok('find -name "*.pyc" -delete')
        if action == "clean":
            run_as_addok('git clean -df')
        execute(install)


@task
@roles('web')
def install():
    """
    Update the requirements.
    """
    puts('Installing...')
    cmd = '{virtualenv_dir}/bin/python setup.py develop'
    run_as_addok(cmd.format(**env))


@task
@roles('web')
def shell():
    cmd = "{virtualenv_dir}/bin/python /home/addok/src/run.py shell"
    run_as_addok(cmd.format(virtualenv_dir=env.virtualenv_dir))


@task
def deploy(verbosity='normal'):
    """
    Full server deploy.

    Updates the repository (server-side) and restarts the web service.
    """
    if verbosity == 'noisy':
        hide_args = []
    else:
        hide_args = ['running', 'stdout']
    with hide(*hide_args):
        puts('Updating repository...')
        execute(update)
        puts('Restarting web server...')
        execute(restart)
