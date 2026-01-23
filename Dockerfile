# Use Apify's Playwright base image
FROM apify/actor-node-playwright-chrome:20

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install --include=dev

# Copy source code
COPY . ./

# Run the actor
CMD npm start
