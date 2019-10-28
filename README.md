# Transformer Template
A template for creating transformers for multiple environments.

## Quick Start
To use this template:
1. Clone this template into a new repository
2. Fill out the `configuration.py` file with your information. Feel free to add additional variables.
3. Add your code to the `transformer.py` file, filling in the *add_parameters*, *check_continue*, and *perform_process* functions.
4. Run the `generate-docker.py` script to generate your Dockerfile for building images
5. Build the Docker image for your transformer, being sure to specify the desired source image

For your transformer to be accepted, be sure to have test cases and continuous integration setup.
Please be sure to read about how to contribute in the documents held in our [main repository](https://github.com/AgPipeline/Organization-info).

## Extending the Template
There are situations where this template won't be sufficient as a transformer for an environment.
In these cases it's recommended that instead of forking this repo and making modifications, a new template repo is created with the expectation that the processing code will be a submodule to it.
Scripts and/or instructions can then be provided on cloning this repo, specifying the submodule, and how to create a working transformer for the environment.

The benefit of this approach is that the processing code can be updated in its original repo, and a clear update path is available to create an updated transformer for the environment.
Another benefit is the clean separation of the processing logic and the environment via seperate repos.

A drawback is that there may be a proliferation of repos.

