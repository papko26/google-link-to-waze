# Start with the official lightweight Python image based on Alpine
FROM python:3.12-alpine

# Set the working directory inside the container
WORKDIR /app

# Copy the Python script into the container
COPY gtw.py /app/app.py

# Install dependencies
RUN pip install -r requirements.txt

# Expose the web server port
EXPOSE 5000

# Command to run the Flask app
CMD ["python", "/app/app.py"]