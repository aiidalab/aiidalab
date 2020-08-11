# Used this command on 2019-04-25
pip install aiida-core[rest,atomic_tools]==1.0.0b2 git+https://github.com/aiidateam/aiida-quantumespresso@e5e1a4b47e7d19c59af8174157d7eb65a3b9292d#egg=aiida_quantumespresso aiida-zeopp==1.0.0a2 aiida-qeq==1.0.0a1 aiida-diff==1.0.0a1 aiida-cp2k==1.0.0b1 appmode-aiidalab bokeh bqplot cookiecutter dulwich fileupload html5lib ipympl "ipython<6.0" lxml nglview pythreejs requests-cache "tornado<5"

# (may have to remove aiidalab dependency)
pip freeze > requirements.txt
