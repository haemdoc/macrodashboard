# MacroDashboard

## Overview
MacroDashboard is a powerful tool designed for managing and visualizing macroeconomic data efficiently. It allows users to analyze trends, generate reports, and make data-driven decisions using our intuitive interface.

## Features
- **Data Visualization**: Dynamic charts and graphs to represent macroeconomic data.
- **Real-time Updates**: Automatic fetching of the latest data to keep your reports up-to-date.
- **Custom Reports**: Generate reports tailored to specific requirements.
- **User Management**: Manage user roles and permissions to control data access.
- **Responsive Design**: Accessible from both desktop and mobile devices.

## Setup Instructions
1. **Clone the Repository**:
   ```
git clone https://github.com/haemdoc/macrodashboard.git
cd macrodashboard
```
2. **Install Dependencies**:
   Make sure you have [Node.js](https://nodejs.org/) (version x.x.x) installed. Then run:
   ```
npm install
```
3. **Configure Environment Variables**:
   Create a `.env` file based on the provided `.env.example` file and ensure you fill in the required configuration values.

## Deployment Guide
1. **Build the Application**:
   ```
npm run build
```
2. **Start the Server**:
   ```
npm start
```
   The application will run on [http://localhost:3000](http://localhost:3000).

3. **Production Deployment**:
   For production environments, consider using a service like [Heroku](https://www.heroku.com/) or [AWS](https://aws.amazon.com/) and follow their specific deployment instructions.

## API Key Configuration
To use external APIs, you need to set your API keys in the `.env` file:
- `API_KEY` = Your API Key for accessing the specific data APIs.
- Additional keys may be required based on the specific integrations you choose to implement in the Dashboard.

**Note**: Never expose your `.env` file to version control. Add it to your `.gitignore` file.

## Contributing
Contributions are welcome! Please read our contributing guidelines before submitting any pull requests.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
