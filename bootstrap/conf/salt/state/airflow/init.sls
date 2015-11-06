upgrade_pip:
  cmd.run:
    - name: pip install -U pip
  
install_numpy:
  pip.installed: 
    - name: numpy
  
install_airflow:
  pip.installed: 
    - name: airflow
    
/root/airflow/airflow.cfg:
  file.managed:
    - source: salt://airflow/conf/airflow.cfg
    - user: postgres
    - group: postgres
    - mode: 600
    - makedirs: True