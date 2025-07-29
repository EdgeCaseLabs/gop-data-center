# GOP Data Center Voter Lookup

Automated voter lookup script for the GOP Data Center website using Playwright browser automation.

## Features

- Secure credential storage with encryption
- Automated login and search
- Bulk voter searches
- Export results to JSON or CSV
- Runs headless by default (no browser window)
- Debug mode for troubleshooting with visible browser
- Search filters (address, city, zip, phone, voter ID)

## Installation

### Using uv (Recommended)

1. Install [uv](https://github.com/astral-sh/uv) if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone this repository and make the script executable:
```bash
git clone <repository-url>
cd gop-data-center
chmod +x gop_voter_lookup.py
```

That's it! The script will automatically install dependencies and browsers when you run it.

### Traditional Installation

1. Clone this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```


## Usage

### Basic Search

#### With uv (Recommended)
Search for a single voter:
```bash
./gop_voter_lookup.py "John Doe"
```

Or use uv run directly:
```bash
uv run gop_voter_lookup.py "John Doe"
```

Search for multiple voters:
```bash
./gop_voter_lookup.py "John Doe" "Jane Smith" "Robert Johnson"
```

#### Traditional Method
```bash
python gop_voter_lookup.py "John Doe"
```

### First Run
On first run, the script will prompt for your GOP Data Center credentials:
```
GOP Data Center credentials not found.
Please enter your credentials (they will be encrypted and saved locally)
Username: your_username
Password: [hidden input]
```

Credentials are encrypted and stored locally in `.credentials` (excluded from git).

### Command Line Options

All examples below work with both `./gop_voter_lookup.py` (uv) or `python gop_voter_lookup.py`:

```bash
# Basic search (runs in headless mode by default)
./gop_voter_lookup.py "John Doe"

# Debug mode: shows browser and keeps it open for troubleshooting
./gop_voter_lookup.py "John Doe" --debug

# Export results to JSON
./gop_voter_lookup.py "John Doe" --export json --output results.json

# Export results to CSV
./gop_voter_lookup.py "John Doe" --export csv --output results.csv

# Search with filters
./gop_voter_lookup.py "John Doe" --city Houston --zip 77001

# Delete stored credentials
./gop_voter_lookup.py --delete-credentials
```

### Available Filters
- `--address`: Filter by address
- `--city`: Filter by city
- `--zip`: Filter by zip code
- `--phone`: Filter by phone number
- `--voter-id`: Filter by voter ID

## Security

- Credentials are encrypted using Fernet symmetric encryption
- Encryption key is stored separately from credentials
- Both files have restricted permissions (600)
- Never commit `.credentials` or `.key` files

## Output Format

### Console Output
```
Searching for: John Doe
Found 1 result(s)

=== Results for John Doe ===

Result 1:
  name: DOE, JOHN M.
  address: 123 Main St
  city: Houston
  state: TX
  zip_code: 77001
  phone: (713)555-1234
  date_of_birth: 05/15/1965
  calculated_party: 2 - Soft Republican
```

### JSON Export
```json
{
  "John Doe": [
    {
      "name": "DOE, JOHN M.",
      "address": "123 Main St",
      "city": "Houston",
      "state": "TX",
      "zip_code": "77001",
      "phone": "(713)555-1234",
      "date_of_birth": "05/15/1965",
      "calculated_party": "2 - Soft Republican",
      "voter_id": null,
      "precinct": null,
      "status": null
    }
  ]
}
```

## Troubleshooting

### Authentication Issues
- Verify your credentials are correct
- Delete stored credentials and re-enter: `./gop_voter_lookup.py --delete-credentials`

### Browser Issues
- Browsers are installed automatically on first run
- If you encounter browser errors, try deleting the `.venv` folder and running again

### Search Issues
- The script uses "Closest Match" search by default
- Try being more specific with search terms
- Use filters to narrow results
- Use `--debug` mode to see exactly what's happening:
  ```bash
  ./gop_voter_lookup.py "John Doe" --debug
  ```
  This will:
  - Show the browser window
  - Print navigation steps
  - Display search parameters
  - Keep the browser open after searching (press Enter to close)

## License

This script is for authorized use only. Ensure you have permission to access the GOP Data Center.