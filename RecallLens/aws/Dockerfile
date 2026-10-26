FROM public.ecr.aws/lambda/python:3.13

COPY requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt
RUN pip install --no-cache-dir --requirement ${LAMBDA_TASK_ROOT}/requirements.txt

COPY handler.py ${LAMBDA_TASK_ROOT}/handler.py
COPY sharing.py ${LAMBDA_TASK_ROOT}/sharing.py
CMD ["handler.lambda_handler"]
