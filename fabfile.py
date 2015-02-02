from fabric.api import task, env, roles, cd, hide, sudo, execute, puts


env.project_name = 'addok'
env.repository = 'https://github.com/etalab/addok.git'
env.local_branch = 'master'
env.remote_ref = 'origin/master'
env.requirements_file = 'requirements.txt'
env.use_ssh_config = True
env.shell = "/bin/bash -c"  # Default uses -l option that we don't want.


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
def live():
    """
    Use the live deployment environment on Etalab servers.
    You need the "ban" server to be referenced in your ~/.ssh/config file.
    """
    server = 'ban'
    env.roledefs = {
        'web': [server],
    }
    env.system_users = {server: 'addok'}
    env.virtualenv_dir = '/home/addok/.virtualenvs/addok'
    env.project_dir = '/home/addok/src/'
    env.restart_command = 'pkill -HUP gunicorn'

# Set the default environment.
live()


# =============================================================================
# Actual tasks
# =============================================================================

@task
@roles('web')
def install():
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
    sudo(env.restart_command)


@task
@roles('web')
def update(action='check'):
    """
    Update the repository (server-side).

    By default, if the requirements file changed in the repository then the
    requirements will be updated. Use ``action='force'`` to force
    updating requirements. Anything else other than ``'check'`` will avoid
    updating requirements at all.
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
        if action == 'check':
            reqs_changed = env.requirements_file in changed_files
        else:
            reqs_changed = False
        run_as_addok('git merge {remote_ref}'.format(**env))
        run_as_addok('find -name "*.pyc" -delete')
        if action == "clean":
            run_as_addok('git clean -df')
    if reqs_changed or action == 'force':
        execute(requirements)


@task
@roles('web')
def requirements():
    """
    Update the requirements.
    """
    base_command = '{virtualenv_dir}/bin/pip install'.format(
        virtualenv_dir=env.virtualenv_dir)
    kw = {
        "base_command": base_command,
        "project_dir": env.project_dir,
        "requirements_file": env.requirements_file,
    }
    cmd = '{base_command} -r {project_dir}/{requirements_file}'.format(**kw)
    run_as_addok(cmd)


@task
@roles('web')
def shell():
    cmd = "{virtualenv_dir}/bin/python /home/addok/addok/run.py shell"
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
