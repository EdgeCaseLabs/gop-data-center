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
- Optional detailed voter information extraction from individual voter pages
- Direct links to voter detail pages for manual browsing

## Installation

### Using uv (Recommended)

1. Install [uv](https://github.com/astral-sh/uv) if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone this repository
```bash
git clone <repository-url>
cd gop-data-center
```

That's it! The script will automatically install dependencies and browsers when you run it.


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

# Extract detailed voter information (slower but more comprehensive)
./gop_voter_lookup.py "John Doe" --extract-details

# Combine detailed extraction with other options
./gop_voter_lookup.py "John Doe" --extract-details --export json --output detailed_results.json

# Delete stored credentials
./gop_voter_lookup.py --delete-credentials
```

### Available Options

#### Search Filters
- `--address`: Filter by address
- `--city`: Filter by city
- `--zip`: Filter by zip code
- `--phone`: Filter by phone number
- `--voter-id`: Filter by voter ID

#### Additional Options
- `--extract-details`: Extract comprehensive voter information from individual detail pages (slower)
- `--debug`: Show browser window and detailed debugging information
- `--export`: Export results to JSON or CSV format
- `--output`: Specify output filename for exports

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
  📄 View Full Details: https://www.gopdatacenter.com/rnc/RecordLookup/RecordMaintenance.aspx?id=12345
```

The "📄 View Full Details" link provides direct access to the voter's complete profile page on the GOP Data Center, allowing you to manually browse additional information or verify the automated extraction results.

### Detailed Information (--extract-details)
When using the `--extract-details` flag, the script extracts comprehensive information from individual voter detail pages:

```
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

  --- Detailed Information ---

  Personal:
    first_name: JOHN
    middle_name: M
    last_name: DOE
    gender: M
    birthday: 05/15/1965
    age: 58

  Contact:
    email: john.doe@example.com
    home_phone: (713)555-1234
    work_phone: (713)555-5678
    cell_phone: (713)555-9999

  Voter Info:
    voter_id: TX1234567890
    registration_date: 01/15/1990
    party_affiliation: Republican
    voter_status: Active
    precinct: 123

  Districts:
    district_congress: 7
    district_state_house: 134
    district_state_senate: 11
```

**Note:** Detailed extraction is significantly slower as it must visit each voter's individual detail page.

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

This script is for authorized use only. Ensure you have permission to access the GOP Data Center and follow the terms of usage.
