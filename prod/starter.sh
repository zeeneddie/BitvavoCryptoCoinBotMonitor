result=1
while [ $result -ne 0 ]; do
    python monitor.py
    result=$?
    echo result
done
