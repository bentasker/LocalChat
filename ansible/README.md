LocalChat Ansible Playbook Instructions
=========================================



Dependancies
----------------

Requires ansible >= 2.2



Usage
------

Edit `inventory/hosts` to add your new hosts in, and then trigger ansible as so:

    ansible-playbook localchat-servers.yml -i inventory/  -v
    
