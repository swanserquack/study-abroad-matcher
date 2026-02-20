### Setting up the development environment
To set up the development environment for this project, please follow these steps:
1. Clone the repository to your local machine using `git clone <repository_url>`.
2. Ensure you have [uv](https://docs.astral.sh/uv/) installed on your system.
3. Navigate to the project directory and run `uv sync` to install the required dependencies as specified in the `pyproject.toml` file.
4. You can now run the project using `uv run main.py` for the main entry point.


### Adding a new provider
If you want to add a new provider, please follow these steps:
1. Fork the repository and create a new branch for your provider.
2. Place your provider's python file under its respective country's folder in the `providers` directory. For example, if you are adding a provider for the United States, you would place it in `providers/united_states/`. If no such folder exists, you can create one.
3. Make sure your provider's python file follows the naming convention of `provider_name.py`.
4. Create a class in your provider's python file that inherits from the `BaseProvider` class. The class name should be in CamelCase and should reflect the provider's name. For example, if your provider is "University of California", you could name your class `UniversityOfCaliforniaProvider`.
5. Implement the required methods in your provider class, such as `search_by_keyword` and any other methods necessary for scraping the provider's course data. Make sure the `university_name` attribute is set to the name of the university or institution you are scraping from and is unique. Ensure that your provider returns data in the expected format as defined by the `CourseList` and `CourseData` data models. You can refer to existing providers for examples of how to implement these methods.
6. Document your code with comments to explain the logic and any important details about how your provider works. This will help other contributors understand your code and make it easier for them to maintain it in the future. Additionally, consider adding docstrings to your methods to provide clear explanations of their functionality and expected inputs/outputs.
7. Test your provider to ensure it is working correctly and returning the expected data.
8. Once you are satisfied with your provider, create a pull request to merge your changes into the main branch. Please provide a clear description of the changes you made and any relevant information about the provider you added.
9. After your pull request is reviewed and approved, it will be merged into the main branch, and your provider will be added to the project. Thank you for contributing!


### Editing an existing provider
If you want to edit an existing provider, please follow these steps:
1. Fork the repository and create a new branch for your edits.
2. Navigate to the provider's python file that you want to edit. It should be located in the `providers` directory under its respective country's folder.
3. Read the existing code and comments to understand how the provider works and what changes you want to make. If you are fixing a bug, try to identify the root cause of the issue before making any changes to ensure the issue lies with the provider's implementation and not with the data models or other parts of the system.
4. Make the necessary changes to the provider's code. This could include fixing bugs, improving the scraping logic, updating the data models, or adding new features. Make sure to test your changes to ensure they work correctly and do not break any existing functionality.
5. Edit current comments or add new comments to explain the changes you made.
6. Once you are satisfied with your edits, create a pull request to merge your changes into the main branch. Please provide a clear description of the changes you made and any relevant information about the provider you edited.
7. After your pull request is reviewed and approved, it will be merged into the main branch, and your edits will be added to the project. Thank you for contributing!

### Editing the central systems (data models, engine, etc.)
If you want to edit the central systems of the project, such as the data models or the engine, please follow these steps:
1. Fork the repository and create a new branch for your edits.
2. Navigate to the file that you want to edit. This could be in the `models.py` file for data models or the `engine.py` file for the engine.
3. Read the existing code and comments to understand how the system works and what changes you want to make. If you are fixing a bug, try to identify the root cause of the issue before making any changes to ensure the issue lies with the system's implementation and not with the providers or other parts of the project. If you are adding a new feature, make sure to consider how it will affect the existing functionality and whether it is compatible with the current design of the system.
4. Make the necessary changes to the system's code. This could include fixing bugs, improving the logic, updating the data models, or adding new features.
5. Since changes to the central systems affect all providers, it is crucial to thoroughly test your changes to ensure they work correctly and do not break any existing functionality with **any** provider. Consider writing unit tests for your changes if applicable.
6. Edit current comments or add new comments to explain the changes you made and how they affect the system. This will help other contributors understand your changes and how to work with the updated system.
7. Once you are satisfied with your edits, create a pull request to merge your changes into the main branch. Please provide a clear description of the changes you made and any relevant information about how they affect the system.
8. After your pull request is reviewed and approved, it will be merged into the main branch, and your edits will be added to the project. Thank you for contributing!