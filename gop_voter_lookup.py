#!/usr/bin/env -S uv run
"""
GOP Data Center Voter Lookup Script
Automates voter searches on the GOP Data Center website
"""

import asyncio
import os
import json
import csv
import getpass
import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime

from playwright.async_api import async_playwright, Page
from playwright._impl._errors import Error as PlaywrightError
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow


@dataclass
class VoterRecord:
    """Structure for basic voter information from search results"""
    name: str
    address: str
    city: str
    state: str
    zip_code: str
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    calculated_party: Optional[str] = None
    view_voter_url: Optional[str] = None
    voter_id: Optional[str] = None
    precinct: Optional[str] = None
    status: Optional[str] = None


@dataclass  
class DetailedVoterRecord:
    """Structure for comprehensive voter information from detail pages"""
    # Basic identification
    name: str
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    
    # Personal information
    birthday: Optional[str] = None
    age: Optional[str] = None
    gender: Optional[str] = None
    
    # Contact information
    mobile_phone: Optional[str] = None
    mobile_phone_reliability: Optional[str] = None
    landline_phone: Optional[str] = None
    landline_phone_reliability: Optional[str] = None
    primary_address: Optional[str] = None
    secondary_address: Optional[str] = None
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    twitter: Optional[str] = None
    
    # Voter registration information
    registration_status: Optional[str] = None
    registration_date: Optional[str] = None
    last_activity_date: Optional[str] = None
    official_party: Optional[str] = None
    observed_party: Optional[str] = None
    calculated_party: Optional[str] = None
    absentee_status: Optional[str] = None
    
    # Ethnicity information
    state_reported_ethnicity: Optional[str] = None
    modeled_ethnicity: Optional[str] = None
    observed_ethnicity: Optional[str] = None
    
    # Voter identification numbers
    gopdc_voter_key: Optional[str] = None
    rnc_client_id: Optional[str] = None
    state_voter_id: Optional[str] = None
    jurisdictional_voter_id: Optional[str] = None
    rnc_registration_id: Optional[str] = None
    
    # District information
    congressional_district: Optional[str] = None
    senate_district: Optional[str] = None
    legislative_district: Optional[str] = None
    jurisdiction: Optional[str] = None
    precinct: Optional[str] = None
    precinct_number: Optional[str] = None
    custom_districts: Optional[List[str]] = None
    
    # Vote history information
    early_vote_date: Optional[str] = None
    vote_history: Optional[Dict[str, Dict[str, str]]] = None
    
    # Voter frequency scores
    overall_frequency: Optional[str] = None
    general_frequency: Optional[str] = None
    primary_frequency: Optional[str] = None
    voter_regularity_general: Optional[str] = None
    voter_regularity_primary: Optional[str] = None
    
    # Geographic information
    dma: Optional[str] = None
    census_block: Optional[str] = None
    turf: Optional[str] = None
    
    # Tags and categorization
    tags: Optional[List[str]] = None
    
    # Notes
    notes: Optional[List[str]] = None
    

class GoogleSheetsManager:
    """Manages Google Sheets integration for bulk voter lookup"""
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    def __init__(self, project_dir: Path, debug: bool = False):
        self.project_dir = project_dir
        self.debug = debug
        self.token_file = project_dir / "token.json"
        self.credentials_file = project_dir / "credentials.json"
        self.service = None
        
    def authenticate(self):
        """Authenticate with Google Sheets API"""
        creds = None
        
        # First, try Service Account authentication (recommended for local use)
        service_account_file = self.project_dir / "service-account.json"
        if service_account_file.exists():
            if self.debug:
                print(f"🔑 Using Service Account authentication: {service_account_file}")
            try:
                creds = ServiceAccountCredentials.from_service_account_file(
                    str(service_account_file), 
                    scopes=self.SCOPES
                )
                self.service = build('sheets', 'v4', credentials=creds)
                if self.debug:
                    print("✅ Service Account authentication successful")
                return True
            except Exception as e:
                print(f"❌ Service Account authentication failed: {e}")
                print("   Falling back to OAuth authentication...")
        
        # Fallback to OAuth authentication
        # Load existing token
        if self.token_file.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_file), self.SCOPES)
            
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    if self.debug:
                        print(f"Token refresh failed: {e}")
                    print("⚠️  Token refresh failed, need to re-authenticate")
                    # Remove invalid token to force re-auth
                    if self.token_file.exists():
                        self.token_file.unlink()
                    creds = None
            else:
                if not self.credentials_file.exists():
                    print("\n❌ Google API credentials not found!")
                    print("\n🔧 Recommended: Set up Service Account (easier for local use):")
                    print("   1. Visit: https://console.cloud.google.com/")
                    print("   2. Create a project (or select existing)")
                    print("   3. Enable Google Sheets API:")
                    print("      https://console.cloud.google.com/apis/library/sheets.googleapis.com")
                    print("   4. Go to Credentials:")
                    print("      https://console.cloud.google.com/apis/credentials")
                    print("   5. Click '+ CREATE CREDENTIALS' → 'Service account'")
                    print("   6. Fill in service account details")
                    print("   7. Click 'CREATE AND CONTINUE' → Skip roles → 'DONE'")
                    print("   8. Click on the created service account")
                    print("   9. Go to 'Keys' tab → 'ADD KEY' → 'Create new key' → JSON")
                    print("   10. Download JSON file and save it as:")
                    print(f"       {service_account_file}")
                    print("   11. Share your Google Sheet with the service account email from the JSON")
                    print("\n🔧 Alternative: OAuth Setup (requires consent screen):")
                    print("   • Create OAuth 2.0 Client ID instead")
                    print("   • Download as credentials.json")
                    print(f"   • File should start with: {{\"installed\":{{...}}")
                    return False
                    
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_file), self.SCOPES)
                    print("\n🔐 Opening browser for Google authentication...")
                    print("   If browser doesn't open, copy the URL from the terminal")
                    creds = flow.run_local_server(port=0)
                    print("✅ Authentication successful!")
                except Exception as e:
                    print(f"\n❌ Authentication failed: {e}")
                    print("   Please check your credentials.json file format")
                    return False
                
            # Save credentials for next run
            try:
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
                if self.debug:
                    print(f"✅ Saved token to {self.token_file}")
            except Exception as e:
                if self.debug:
                    print(f"⚠️  Could not save token: {e}")
                
        try:
            self.service = build('sheets', 'v4', credentials=creds)
            if self.debug:
                print("✅ Google Sheets service initialized")
            return True
        except Exception as e:
            print(f"❌ Failed to initialize Google Sheets service: {e}")
            return False
        
    def list_spreadsheets(self):
        """List available spreadsheets (requires Drive API - simplified for now)"""
        # For now, user needs to provide spreadsheet ID directly
        # Could be enhanced to list spreadsheets with Drive API
        pass
        
    def get_spreadsheet_info(self, spreadsheet_id: str):
        """Get information about a spreadsheet"""
        try:
            sheet = self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            return {
                'title': sheet.get('properties', {}).get('title', 'Unknown'),
                'sheets': [s['properties']['title'] for s in sheet.get('sheets', [])]
            }
        except Exception as e:
            if self.debug:
                print(f"Error getting spreadsheet info: {e}")
            return None
            
    def read_column(self, spreadsheet_id: str, sheet_name: str, column: str, start_row: int = 2, row_limit: int = None):
        """Read names from a specific column, returning names and their row numbers"""
        try:
            # Convert column letter to range (e.g., 'A' -> 'A2:A')
            range_name = f"{sheet_name}!{column}{start_row}:{column}"
            
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            
            # Process rows and track valid entries with their row numbers
            valid_entries = []
            processed_count = 0
            
            for i, row in enumerate(values):
                actual_row_num = start_row + i
                
                # Skip empty rows
                if not row or not row[0] or not row[0].strip():
                    if self.debug:
                        print(f"  Skipping empty row {actual_row_num}")
                    continue
                
                name = row[0].strip()
                valid_entries.append({
                    'name': name,
                    'row': actual_row_num
                })
                processed_count += 1
                
                # Check row limit
                if row_limit and processed_count >= row_limit:
                    if self.debug:
                        print(f"  Reached row limit of {row_limit} valid entries")
                    break
            
            if self.debug:
                print(f"Read {len(valid_entries)} valid names from {sheet_name}!{column}")
                if row_limit:
                    print(f"  Applied row limit: {row_limit}")
                
            return valid_entries
            
        except Exception as e:
            if self.debug:
                print(f"Error reading column: {e}")
            return []
            
    def update_row(self, spreadsheet_id: str, sheet_name: str, row_num: int, voter_data: dict, column_mapping: dict):
        """Update a row with voter data"""
        try:
            # Prepare the values to update based on column mapping
            updates = []
            
            for field, column in column_mapping.items():
                if field in voter_data and voter_data[field]:
                    value = voter_data[field]
                    # Handle list values (like notes)
                    if isinstance(value, list):
                        value = '; '.join(str(v) for v in value)
                    
                    range_name = f"{sheet_name}!{column}{row_num}"
                    updates.append({
                        'range': range_name,
                        'values': [[str(value)]]
                    })
                    
                    if self.debug:
                        print(f"    Mapping {field} = '{value}' -> {column}{row_num}")
                    
            if updates:
                # Batch update for efficiency
                body = {'valueInputOption': 'RAW', 'data': updates}
                
                result = self.service.spreadsheets().values().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body=body
                ).execute()
                
                if self.debug:
                    print(f"Updated row {row_num} with {len(updates)} fields")
                    
                return True
                
        except Exception as e:
            if self.debug:
                print(f"Error updating row {row_num}: {e}")
            return False
            
    def get_column_headers(self, spreadsheet_id: str, sheet_name: str, header_row: int = 1):
        """Get column headers to help with mapping"""
        try:
            range_name = f"{sheet_name}!{header_row}:{header_row}"
            
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [[]])
            headers = values[0] if values else []
            
            # Create a mapping of header -> column letter
            column_map = {}
            for idx, header in enumerate(headers):
                if header.strip():
                    col_letter = chr(65 + idx)  # A, B, C, ...
                    column_map[header.strip().lower()] = col_letter
                    
            return column_map
            
        except Exception as e:
            if self.debug:
                print(f"Error getting headers: {e}")
            return {}
            
    def column_letter_to_number(self, column_letter: str) -> int:
        """Convert column letter (A, B, C, etc.) to column number (1, 2, 3, etc.)"""
        result = 0
        for char in column_letter.upper():
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result
        
    def column_number_to_letter(self, column_number: int) -> str:
        """Convert column number (1, 2, 3, etc.) to column letter (A, B, C, etc.)"""
        result = ""
        while column_number > 0:
            column_number -= 1
            result = chr(column_number % 26 + ord('A')) + result
            column_number //= 26
        return result
        
    def generate_column_mapping(self, start_column: str, extract_details: bool = False):
        """Generate sequential column mapping starting from the specified column"""
        start_num = self.column_letter_to_number(start_column)
        
        # Define the order of basic fields
        basic_fields = [
            'phone', 'address', 'city', 'state', 'zip_code', 
            'date_of_birth', 'calculated_party', 'view_voter_url'
        ]
        
        # Define additional detailed fields if extract_details is enabled
        detailed_fields = [
            'first_name', 'middle_name', 'last_name', 'birthday', 'age', 'gender',
            'mobile_phone', 'landline_phone', 'primary_address', 'secondary_address',
            'registration_status', 'registration_date', 'official_party', 'observed_party',
            'modeled_ethnicity', 'gopdc_voter_key', 'rnc_client_id', 'state_voter_id',
            'congressional_district', 'senate_district', 'legislative_district', 
            'jurisdiction', 'precinct'
        ]
        
        # Use basic fields, or basic + detailed based on extract_details flag
        fields_to_use = basic_fields
        if extract_details:
            fields_to_use = basic_fields + detailed_fields
        
        # Generate mapping
        column_mapping = {}
        for i, field in enumerate(fields_to_use):
            column_letter = self.column_number_to_letter(start_num + i)
            column_mapping[field] = column_letter
            
        return column_mapping, fields_to_use
        
    def check_row_already_processed(self, spreadsheet_id: str, sheet_name: str, row_num: int, start_column: str):
        """Check if a row already has data in the start column (indicating it's been processed)"""
        try:
            # Read the start column cell for this specific row
            range_name = f"{sheet_name}!{start_column}{row_num}"
            
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            
            # If there's any data in the start column, consider it processed
            if values and values[0] and len(values[0]) > 0 and values[0][0].strip():
                return True
            
            return False
            
        except Exception as e:
            if self.debug:
                print(f"Warning: Could not check if row {row_num} is processed: {e}")
            # If we can't check, assume it's not processed to be safe
            return False

class CredentialManager:
    """Manages secure storage and retrieval of credentials"""
    
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.credentials_file = project_dir / ".credentials"
        self.key_file = project_dir / ".key"
        
    def _generate_key(self) -> bytes:
        """Generate a new encryption key"""
        key = Fernet.generate_key()
        self.key_file.write_bytes(key)
        self.key_file.chmod(0o600)  # Restrict permissions
        return key
        
    def _get_key(self) -> bytes:
        """Get or create encryption key"""
        if self.key_file.exists():
            return self.key_file.read_bytes()
        return self._generate_key()
        
    def check_credentials(self) -> bool:
        """Check if credentials exist"""
        return self.credentials_file.exists()
        
    def prompt_credentials(self) -> tuple[str, str]:
        """Prompt user for credentials"""
        print("\nGOP Data Center credentials not found.")
        print("Please enter your credentials (they will be encrypted and saved locally)")
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ")
        return username, password
        
    def save_credentials(self, username: str, password: str) -> None:
        """Encrypt and save credentials"""
        fernet = Fernet(self._get_key())
        
        credentials = {
            "username": username,
            "password": password
        }
        
        encrypted_data = fernet.encrypt(json.dumps(credentials).encode())
        self.credentials_file.write_bytes(encrypted_data)
        self.credentials_file.chmod(0o600)  # Restrict permissions
        print("✓ Credentials saved successfully")
        
    def load_credentials(self) -> tuple[str, str]:
        """Load and decrypt credentials"""
        fernet = Fernet(self._get_key())
        encrypted_data = self.credentials_file.read_bytes()
        decrypted_data = fernet.decrypt(encrypted_data)
        credentials = json.loads(decrypted_data.decode())
        return credentials["username"], credentials["password"]
        
    def delete_credentials(self) -> None:
        """Delete stored credentials"""
        if self.credentials_file.exists():
            self.credentials_file.unlink()
        if self.key_file.exists():
            self.key_file.unlink()
        print("✓ Credentials deleted")


class GOPVoterLookup:
    """Main class for GOP voter lookup automation"""
    
    def __init__(self, headless: bool = True, debug: bool = False, extract_details: bool = False):
        self.headless = headless
        self.debug = debug
        self.extract_details = extract_details
        self.base_url = "https://www.gopdatacenter.com/rnc/RecordLookup/RecordLookup.aspx"
        self.credential_manager = CredentialManager(Path.cwd())
        
    @staticmethod
    def _check_and_install_browsers():
        """Ensure Playwright browsers are available"""
        print("Checking if Playwright browsers are available...")
        try:
            # Always run install - Playwright will skip if already installed
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], 
                         check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to install Playwright browsers: {e}")
            print("Please run manually: uv run playwright install chromium")
            sys.exit(1)
        
    async def _authenticate(self, page: Page, username: str, password: str) -> bool:
        """Authenticate with the GOP Data Center"""
        try:
            # Wait for login form
            await page.wait_for_selector('input[name*="UserName"]', timeout=10000)
            
            # Fill credentials
            await page.fill('input[name*="UserName"]', username)
            await page.fill('input[name*="Password"]', password)
            
            # Click login button
            await page.click('input[type="submit"][value="Log In"]')
            
            # Wait for navigation or error
            await page.wait_for_load_state("networkidle", timeout=15000)
            
            # Check if we're on the search page
            if "RecordLookup.aspx" in page.url:
                print("✓ Successfully authenticated")
                return True
            else:
                print("✗ Authentication failed")
                return False
                
        except Exception as e:
            print(f"✗ Authentication error: {e}")
            return False
            
    async def _search_voter(self, page: Page, voter_name: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for a voter and return results"""
        results = []
        
        try:
            # Clear previous search
            clear_button = page.locator('a:has-text("Clear")')
            if await clear_button.is_visible():
                await clear_button.click()
                await page.wait_for_timeout(500)
            
            # Fill search form - with better error handling
            try:
                # Try using role-based selector first (most reliable)
                name_filled = False
                try:
                    await page.get_by_role('textbox', name='Voter Name').fill(voter_name)
                    name_filled = True
                    if self.debug:
                        print(f"  Filled name field using role selector")
                except:
                    # Fallback to other selectors
                    for selector in ['input[id*="txtName"]', 'input[placeholder*="Voter Name"]', 'input[name*="Name"]']:
                        try:
                            await page.fill(selector, voter_name)
                            name_filled = True
                            if self.debug:
                                print(f"  Filled name field using selector: {selector}")
                            break
                        except:
                            continue
                
                if not name_filled:
                    raise Exception("Could not find voter name input field")
                    
            except Exception as e:
                print(f"Error filling name field: {e}")
                if self.debug:
                    # List all visible input fields for debugging
                    inputs = page.locator('input[type="text"], input[type="search"]')
                    input_count = await inputs.count()
                    print(f"  Available input fields: {input_count}")
                    for idx in range(min(5, input_count)):  # Show first 5
                        inp = inputs.nth(idx)
                        try:
                            field_id = await inp.get_attribute('id') or 'no-id'
                            field_name = await inp.get_attribute('name') or 'no-name'
                            field_placeholder = await inp.get_attribute('placeholder') or 'no-placeholder'
                            print(f"    Input {idx}: id='{field_id}', name='{field_name}', placeholder='{field_placeholder}'")
                        except:
                            pass
                raise
            
            # Optional search parameters
            if kwargs.get('address'):
                await page.fill('input[id*="txtAddress"]', kwargs['address'])
            if kwargs.get('city'):
                await page.fill('input[id*="txtCity"]', kwargs['city'])
            if kwargs.get('zip_code'):
                await page.fill('input[id*="txtZip"]', kwargs['zip_code'])
            if kwargs.get('phone'):
                await page.fill('input[id*="txtPhone"]', kwargs['phone'])
            if kwargs.get('voter_id'):
                await page.fill('input[id*="txtVoterId"]', kwargs['voter_id'])
            
            if self.debug:
                print(f"  Search parameters: name='{voter_name}', {', '.join(f'{k}={v}' for k, v in kwargs.items() if v)}")
                
            # Click search - try multiple possible selectors
            search_clicked = False
            try:
                # Try role-based selector first
                await page.get_by_role('button', name='Search').click()
                search_clicked = True
                if self.debug:
                    print(f"  Clicked search using role selector")
            except:
                # Fallback to other selectors
                for selector in ['input[type="submit"][value="Search"]', 'button:has-text("Search")', 'input[id*="btnSearch"]', 'button[id*="Search"]']:
                    try:
                        await page.click(selector)
                        search_clicked = True
                        if self.debug:
                            print(f"  Clicked search using selector: {selector}")
                        break
                    except:
                        continue
                    
            if not search_clicked:
                raise Exception("Could not find search button")
            
            # Wait for results - handle dynamic content
            if self.debug:
                print("  Waiting for search results to load...")
            
            # Wait for network to be idle
            await page.wait_for_load_state("networkidle", timeout=15000)
            
            # Additional wait for dynamic content - wait for either results table or "no results" message
            try:
                await page.wait_for_selector('table[id*="ResultsGrid"], table[id*="gvResults"], div:has-text("No matching records")', 
                                           state='visible', timeout=10000)
                
                # Give it a bit more time for JavaScript to finish updating the DOM
                await page.wait_for_timeout(1000)
                
            except Exception as e:
                if self.debug:
                    print(f"  Warning: Timeout waiting for results table: {e}")
            
            # Extract results
            results = await self._extract_results(page)
            
        except Exception as e:
            print(f"✗ Search error: {e}")
            
        return results
        
    async def _extract_results(self, page: Page) -> List[Dict[str, Any]]:
        """Extract voter records from search results"""
        results = []
        
        # Check for results table - try multiple possible IDs
        results_table = None
        for table_id in ['table[id*="ResultsGrid"]', 'table[id*="gvResults"]', 'table.results-table']:
            potential_table = page.locator(table_id)
            if await potential_table.is_visible():
                results_table = potential_table
                if self.debug:
                    print(f"  Found results table with selector: {table_id}")
                break
        
        if not results_table:
            if self.debug:
                print("  No results table found on page")
            return results
            
        # Wait a bit for rows to be populated (in case of dynamic loading)
        await page.wait_for_timeout(500)
        
        # Get all result rows - use a more specific selector to exclude header rows
        # Try to get tbody rows first, fall back to all rows
        tbody = results_table.locator('tbody')
        start_row = 1  # Default: skip header row
        if await tbody.count() > 0:
            rows = tbody.locator('tr')
            start_row = 0  # tbody doesn't include header
        else:
            rows = results_table.locator('tr')
            
        row_count = await rows.count()
        
        if self.debug:
            print(f"  Found {row_count} rows in results table (starting from row {start_row})")
            # Also check if there's a specific message about results
            results_text = await results_table.inner_text()
            if "no matching" in results_text.lower() or "0 records" in results_text.lower():
                print("  Table contains 'no matching records' message")
        
        for i in range(start_row, row_count):
            row = rows.nth(i)
            
            try:
                # Extract text content
                row_text = await row.inner_text()
                lines = row_text.strip().split('\n')
                
                if self.debug and i == 1:  # Debug first data row
                    print(f"  First row content ({len(lines)} lines):")
                    for idx, line in enumerate(lines[:5]):  # Show first 5 lines
                        print(f"    Line {idx}: {line[:50]}...")
                
                # Skip if row appears to be empty or too short
                if len(lines) < 2 or all(not line.strip() for line in lines):
                    continue
                    
                if len(lines) >= 2:
                    # Parse voter info - handle different possible structures
                    # Sometimes the first line is a button/action, sometimes it's the name
                    start_idx = 0
                    if lines[0].lower() in ['view', 'select', 'view voter'] or lines[0].strip() == '':
                        start_idx = 1
                    
                    name_line = lines[start_idx] if len(lines) > start_idx else ""
                    address_line = lines[start_idx + 1] if len(lines) > start_idx + 1 else ""
                    city_state_zip = lines[start_idx + 2] if len(lines) > start_idx + 2 else ""
                    
                    # Extract additional info
                    phone = ""
                    dob = ""
                    party = ""
                    view_voter_url = ""
                    
                    # Try to extract View Voter link URL from this row
                    try:
                        # Look for OpenUserWindow() JavaScript function calls
                        row_html = await row.inner_html()
                        
                        if self.debug and i <= 2:  # Debug first 2 rows
                            print(f"    Examining row {i} for OpenUserWindow() function...")
                            print(f"      Row HTML (first 300 chars): {row_html[:300]}...")
                        
                        # Extract record ID from OpenUserWindow(ID) pattern
                        import re
                        open_user_window_match = re.search(r'OpenUserWindow\s*\(\s*(\d+)\s*\)', row_html)
                        
                        if open_user_window_match:
                            record_id = open_user_window_match.group(1)
                            view_voter_url = f"https://www.gopdatacenter.com/rnc/RecordLookup/RecordMaintenance.aspx?id={record_id}"
                            
                            if self.debug:
                                print(f"      Found OpenUserWindow({record_id})")
                                print(f"      Constructed URL: {view_voter_url}")
                        else:
                            if self.debug:
                                print(f"      No OpenUserWindow() function found in row {i}")
                                
                    except Exception as e:
                        if self.debug:
                            print(f"    Warning: Could not extract View Voter URL: {e}")
                    
                    for line in lines[start_idx + 3:]:
                        if line.startswith('('):
                            phone = line
                        elif "DOB:" in line:
                            dob = line.split("DOB:")[-1].strip()
                        elif "Calculated Party:" in line:
                            party = line.split(":")[-1].strip()
                    
                    # Parse city, state, zip
                    city = ""
                    state = ""
                    zip_code = ""
                    if city_state_zip:
                        parts = city_state_zip.split()
                        if len(parts) >= 3:
                            city = " ".join(parts[:-2])
                            state = parts[-2]
                            zip_code = parts[-1]
                    
                    record = VoterRecord(
                        name=name_line.strip(),
                        address=address_line.strip(),
                        city=city,
                        state=state,
                        zip_code=zip_code,
                        phone=phone,
                        date_of_birth=dob,
                        calculated_party=party,
                        view_voter_url=view_voter_url
                    )
                    
                    result_dict = asdict(record)
                    
                    # If detailed extraction is enabled, try to get detailed info
                    if self.extract_details:
                        detailed_info = await self._extract_detailed_info_for_row(page, row, i)
                        if detailed_info:
                            result_dict['detailed_info'] = detailed_info
                    
                    results.append(result_dict)
                    
            except Exception as e:
                print(f"Warning: Error parsing row {i}: {e}")
                continue
                
        return results
        
    async def _extract_detailed_info_for_row(self, page: Page, row_locator, row_index: int) -> Optional[Dict[str, Any]]:
        """Extract detailed voter information by navigating to detail page"""
        try:
            if self.debug:
                print(f"    Attempting to extract detailed info for row {row_index}")
                
            # First, try to extract the View Voter URL from the row
            view_voter_url = None
            
            # Look for OpenUserWindow function in the row HTML
            try:
                row_html = await row_locator.inner_html()
                import re
                open_user_window_match = re.search(r'OpenUserWindow\s*\(\s*(\d+)\s*\)', row_html)
                
                if open_user_window_match:
                    record_id = open_user_window_match.group(1)
                    view_voter_url = f"https://www.gopdatacenter.com/rnc/RecordLookup/RecordMaintenance.aspx?id={record_id}"
                    if self.debug:
                        print(f"      Found voter detail URL: {view_voter_url}")
            except Exception as e:
                if self.debug:
                    print(f"      Could not extract URL from row: {e}")
            
            # If we couldn't get URL from HTML, try clicking the button
            if not view_voter_url:
                view_voter_button = None
                
                # Try different selectors for the View Voter button
                possible_selectors = [
                    'a[id*="ViewVoter"]',
                    'input[id*="ViewVoter"]', 
                    'button[id*="ViewVoter"]',
                    'a:has-text("View Voter")',
                    'input[value*="View"]',
                    'a[title*="View"]'
                ]
                
                for selector in possible_selectors:
                    try:
                        button = row_locator.locator(selector).first
                        if await button.is_visible():
                            view_voter_button = button
                            if self.debug:
                                print(f"      Found View Voter button using selector: {selector}")
                            break
                    except:
                        continue
                
                if not view_voter_button:
                    if self.debug:
                        print(f"      No View Voter button found for row {row_index}")
                    return None
                
            # Get the current number of pages before navigation
            initial_pages = len(page.context.pages)
            
            # Navigate to detail page
            detail_page = None
            
            if view_voter_url:
                # Direct navigation - always open in new tab
                if self.debug:
                    print(f"      Navigating directly to: {view_voter_url}")
                detail_page = await page.context.new_page()
                await detail_page.goto(view_voter_url)
            else:
                # Click the View Voter button
                if self.debug:
                    print(f"      Clicking View Voter button...")
                await view_voter_button.click()
                
                # Wait for new page/tab to open or current page to navigate
                await page.wait_for_timeout(2000)  # Give time for navigation/new tab
                
                current_pages = len(page.context.pages)
                
                if current_pages > initial_pages:
                    # New tab opened
                    detail_page = page.context.pages[-1]  # Get the newest page
                    if self.debug:
                        print(f"      New tab opened, switching to detail page")
                else:
                    # Current page navigated
                    detail_page = page  
                    if self.debug:
                        print(f"      Current page navigated to detail view")
            
            # Wait for the detail page to load
            await detail_page.wait_for_load_state("networkidle", timeout=10000)
            
            if self.debug:
                print(f"      Detail page URL: {detail_page.url}")
                print(f"      Detail page title: {await detail_page.title()}")
            
            # Verify we're on the detail page by checking for specific elements
            is_detail_page = await detail_page.locator('article#personal-info').count() > 0
            
            if not is_detail_page:
                if self.debug:
                    print(f"      Warning: Not on detail page, skipping extraction")
                return None
            
            # Extract detailed information
            detailed_record = await self._extract_detailed_voter_info(detail_page)
            
            if self.debug and detailed_record:
                print(f"      Extracted fields: {[k for k, v in asdict(detailed_record).items() if v is not None]}")
            
            # Close the detail page if needed
            if view_voter_url or (detail_page != page):
                # We opened a new tab
                await detail_page.close()
                if self.debug:
                    print(f"      Closed detail tab")
            else:
                # Current page was used, go back
                await detail_page.go_back()
                await detail_page.wait_for_load_state("networkidle", timeout=5000)
                if self.debug:
                    print(f"      Navigated back to search results")
            
            if detailed_record:
                if self.debug:
                    print(f"      Successfully extracted detailed info for row {row_index}")
                return asdict(detailed_record)
            else:
                if self.debug:
                    print(f"      Failed to extract detailed info for row {row_index}")
                return None
                
        except Exception as e:
            if self.debug:
                print(f"      Error extracting detailed info for row {row_index}: {e}")
            return None
        
    async def _extract_detailed_voter_info(self, page: Page) -> Optional[DetailedVoterRecord]:
        """Extract comprehensive voter information from detail page"""
        try:
            # Wait for the page to load completely
            await page.wait_for_load_state("networkidle", timeout=10000)
            await page.wait_for_timeout(1000)  # Additional wait for dynamic content
            
            if self.debug:
                print("  Extracting detailed voter information...")
            
            # Initialize the detailed record
            detailed_record = DetailedVoterRecord(name="")
            
            # Extract information from each article section
            # Try different selectors for articles
            articles = page.locator('article')
            article_count = await articles.count()
            
            # If no articles found, try divs with class containing article info
            if article_count == 0:
                articles = page.locator('div.search-article')
                article_count = await articles.count()
                
            if self.debug:
                print(f"  Found {article_count} article sections")
            
            for i in range(article_count):
                article = articles.nth(i)
                await self._extract_article_content(article, detailed_record)
            
            return detailed_record
            
        except Exception as e:
            if self.debug:
                print(f"  Error extracting detailed info: {e}")
            return None
    
    async def _extract_article_content(self, article, detailed_record: DetailedVoterRecord):
        """Extract content from a specific article section"""
        try:
            # Get the article content
            article_text = await article.inner_text()
            
            if self.debug:
                print(f"    Processing article with content (first 100 chars): {article_text[:100]}...")
            
            # Determine article type based on content (case-insensitive)
            article_text_upper = article_text.upper()
            
            if "PERSONAL INFO" in article_text_upper:
                await self._extract_personal_info(article, detailed_record)
            elif "CONTACT INFO" in article_text_upper and "OTHER CONTACT" not in article_text_upper:
                await self._extract_contact_info(article, detailed_record)
            elif "VOTER INFO" in article_text_upper:
                await self._extract_voter_info(article, detailed_record)
            elif "VOTER IDENTIFICATION" in article_text_upper:
                await self._extract_voter_identification(article, detailed_record)
            elif "DISTRICT INFO" in article_text_upper:
                await self._extract_district_info(article, detailed_record)
            elif "VOTE HISTORY" in article_text_upper:
                await self._extract_vote_history(article, detailed_record)
            elif "VOTER FREQUENCY" in article_text_upper:
                await self._extract_voter_frequency(article, detailed_record)
            elif "GEOGRAPHICAL LOCATION" in article_text_upper:
                await self._extract_geographical_info(article, detailed_record)
            elif "TAGS" in article_text_upper:
                if self.debug:
                    print(f"    Skipping Tags section as requested")
                # Skip tags as they're not useful
            elif "NOTES" in article_text_upper:
                await self._extract_notes(article, detailed_record)
            else:
                if self.debug:
                    print(f"    Unknown article type, attempting generic extraction...")
                    print(f"    Full article content: {article_text[:300]}...")
                # Try to extract any key-value pairs from unknown articles
                await self._extract_generic_info(article, detailed_record)
                
        except Exception as e:
            if self.debug:
                print(f"  Warning: Error extracting article content: {e}")
    
    async def _extract_personal_info(self, article, detailed_record: DetailedVoterRecord):
        """Extract personal information from Personal Info article"""
        try:
            if self.debug:
                print(f"    Extracting Personal Info...")
            # Extract name components using span IDs
            first_name_elem = article.locator('span[id*="lblFirstName"]')
            if await first_name_elem.count() > 0:
                value = await first_name_elem.inner_text()
                detailed_record.first_name = value
                if self.debug:
                    print(f"      Found first_name: {value}")
                
            middle_name_elem = article.locator('span[id*="lblMiddleName"]')
            if await middle_name_elem.count() > 0:
                detailed_record.middle_name = await middle_name_elem.inner_text()
                
            last_name_elem = article.locator('span[id*="lblLastName"]')
            if await last_name_elem.count() > 0:
                detailed_record.last_name = await last_name_elem.inner_text()
                
            # Construct full name
            if detailed_record.first_name or detailed_record.last_name:
                name_parts = [p for p in [detailed_record.first_name, detailed_record.middle_name, detailed_record.last_name] if p]
                detailed_record.name = " ".join(name_parts)
            
            # Extract birthday
            birthday_elem = article.locator('span[id*="lblBirthday"]')
            if await birthday_elem.count() > 0:
                detailed_record.birthday = await birthday_elem.inner_text()
            
            # Extract age  
            age_elem = article.locator('span[id*="lblAge"]')
            if await age_elem.count() > 0:
                detailed_record.age = await age_elem.inner_text()
                
            # Extract gender
            gender_elem = article.locator('span[id*="lblGender"]')
            if await gender_elem.count() > 0:
                detailed_record.gender = await gender_elem.inner_text()
                
        except Exception as e:
            if self.debug:
                print(f"  Warning: Error extracting personal info: {e}")
    
    async def _extract_contact_info(self, article, detailed_record: DetailedVoterRecord):
        """Extract contact information from Contact Info article"""
        try:
            # Extract phone information - look for phone containers
            phone_containers = article.locator('.col-xs-12.col-sm-3')
            phone_count = await phone_containers.count()
            
            for i in range(phone_count):
                container = phone_containers.nth(i)
                
                # Get all h6 elements in this container
                h6_elements = container.locator('h6')
                if await h6_elements.count() > 0:
                    # Get the first h6 which should be the phone type
                    phone_type = await h6_elements.first.inner_text()
                    
                    # Get phone number - it's in a span right after the phone type h6
                    phone_elem = container.locator('span[id*="lblPhone"]')
                    if await phone_elem.count() > 0:
                        phone_number = await phone_elem.inner_text()
                        
                        # Get TRC (reliability) - it's in a span with lblTRC
                        trc_elem = container.locator('span[id*="lblTRC"]')
                        trc_value = await trc_elem.inner_text() if await trc_elem.count() > 0 else None
                        
                        # Map to appropriate field based on phone type
                        if "Mobile Phone" in phone_type and not phone_number.startswith("No Data"):
                            if not detailed_record.mobile_phone:  # Only set if not already set
                                detailed_record.mobile_phone = phone_number
                                if trc_value:
                                    detailed_record.mobile_phone_reliability = trc_value
                        elif "Landline Phone" in phone_type and not phone_number.startswith("No Data"):
                            if not detailed_record.landline_phone:  # Only set if not already set
                                detailed_record.landline_phone = phone_number
                                if trc_value:
                                    detailed_record.landline_phone_reliability = trc_value
            
            # Extract primary address
            primary_addr_elem = article.locator('span[id*="lblPrimaryAddress"]')
            if await primary_addr_elem.count() > 0:
                addr_line1 = await primary_addr_elem.inner_text()
                # Get city, state, zip
                city_state_zip_elem = article.locator('span[id*="lblPrimaryCityStZip"]')
                if await city_state_zip_elem.count() > 0:
                    city_state_zip = await city_state_zip_elem.inner_text()
                    detailed_record.primary_address = f"{addr_line1}, {city_state_zip}"
                else:
                    detailed_record.primary_address = addr_line1
                    
            # Extract secondary address  
            secondary_addr_elem = article.locator('span[id*="lblSecondaryAddress"]')
            if await secondary_addr_elem.count() > 0:
                addr_line1 = await secondary_addr_elem.inner_text()
                # Get city, state, zip
                city_state_zip_elem = article.locator('span[id*="lblSecondaryCityStZip"]')
                if await city_state_zip_elem.count() > 0:
                    city_state_zip = await city_state_zip_elem.inner_text()
                    detailed_record.secondary_address = f"{addr_line1}, {city_state_zip}"
                else:
                    detailed_record.secondary_address = addr_line1
            
            # Extract social media from repeater pattern
            social_repeaters = article.locator('div[id*="rptSocial"]')
            social_count = await social_repeaters.count()
            
            for i in range(social_count):
                social_container = social_repeaters.nth(i)
                
                # Get social media type from h6
                social_type_elem = social_container.locator('h6').first
                if await social_type_elem.count() > 0:
                    social_type = await social_type_elem.inner_text()
                    
                    # Get social media value
                    social_elem = social_container.locator('span[id*="lblSocial"]')
                    if await social_elem.count() > 0:
                        social_value = await social_elem.inner_text()
                        
                        if social_value and not social_value.startswith("No Data"):
                            if "Facebook" in social_type:
                                detailed_record.facebook = social_value
                            elif "Instagram" in social_type:
                                detailed_record.instagram = social_value
                            elif "Twitter" in social_type:
                                detailed_record.twitter = social_value
                    
        except Exception as e:
            if self.debug:
                print(f"  Warning: Error extracting contact info: {e}")
    
    async def _extract_voter_info(self, article, detailed_record: DetailedVoterRecord):
        """Extract voter registration information"""
        try:
            # Registration status
            reg_status_elem = article.locator('span[id*="lblRegistrationStatus"]')
            if await reg_status_elem.count() > 0:
                detailed_record.registration_status = await reg_status_elem.inner_text()
            
            # Registration date
            reg_date_elem = article.locator('span[id*="lblRegistrationDate"]')
            if await reg_date_elem.count() > 0:
                detailed_record.registration_date = await reg_date_elem.inner_text()
                
            # Last activity date
            last_activity_elem = article.locator('span[id*="lblLastVoterActivity"]')
            if await last_activity_elem.count() > 0:
                detailed_record.last_activity_date = await last_activity_elem.inner_text()
                
            # Official party
            official_party_elem = article.locator('span[id*="lblOfficialParty"]')
            if await official_party_elem.count() > 0:
                detailed_record.official_party = await official_party_elem.inner_text()
                
            # Observed party
            observed_party_elem = article.locator('span[id*="lblParty"]').first
            if await observed_party_elem.count() > 0:
                detailed_record.observed_party = await observed_party_elem.inner_text()
                
            # Calculated party
            calc_party_elem = article.locator('span[id*="lblRNCCalcParty"]')
            if await calc_party_elem.count() > 0:
                detailed_record.calculated_party = await calc_party_elem.inner_text()
                
            # Absentee status
            absentee_status_elem = article.locator('span[id*="lblAbsenteeStatus"]')
            if await absentee_status_elem.count() > 0:
                value = await absentee_status_elem.inner_text()
                if not value.startswith("No Data"):
                    detailed_record.absentee_status = value
                    
            # State reported ethnicity
            state_eth_elem = article.locator('span[id*="lblStateReportedEthnicity"]')
            if await state_eth_elem.count() > 0:
                value = await state_eth_elem.inner_text()
                if value != "No Data Provided":
                    detailed_record.state_reported_ethnicity = value
                    
            # Modeled ethnicity
            modeled_eth_elem = article.locator('span[id*="lblEthnicity"]')
            if await modeled_eth_elem.count() > 0:
                detailed_record.modeled_ethnicity = await modeled_eth_elem.inner_text()
                
            # Observed ethnicity
            observed_eth_elem = article.locator('span[id*="lblObservedEthnicity"]')
            if await observed_eth_elem.count() > 0:
                value = await observed_eth_elem.inner_text()
                if value != "No Data Provided":
                    detailed_record.observed_ethnicity = value
                
        except Exception as e:
            if self.debug:
                print(f"  Warning: Error extracting voter info: {e}")
    
    async def _extract_voter_identification(self, article, detailed_record: DetailedVoterRecord):
        """Extract voter ID numbers"""
        try:
            # GOPDC Voter Key
            gopdc_elem = article.locator('span[id*="lblVoterId"]')
            if await gopdc_elem.count() > 0:
                detailed_record.gopdc_voter_key = await gopdc_elem.inner_text()
                
            # RNC Client ID
            rnc_elem = article.locator('span[id*="lblClientId"]')
            if await rnc_elem.count() > 0:
                detailed_record.rnc_client_id = await rnc_elem.inner_text()
                
            # State Voter ID
            state_elem = article.locator('span[id*="lblStateVoterId"]')
            if await state_elem.count() > 0:
                detailed_record.state_voter_id = await state_elem.inner_text()
                
            # Jurisdictional Voter ID
            jurisdictional_elem = article.locator('span[id*="lblRegistrationId"]')
            if await jurisdictional_elem.count() > 0:
                value = await jurisdictional_elem.inner_text()
                if not value.startswith("No Data"):
                    detailed_record.jurisdictional_voter_id = value
                    
            # RNC Registration ID
            rnc_reg_elem = article.locator('span[id*="lblRncRegId"]')
            if await rnc_reg_elem.count() > 0:
                detailed_record.rnc_registration_id = await rnc_reg_elem.inner_text()
                
        except Exception as e:
            if self.debug:
                print(f"  Warning: Error extracting voter identification: {e}")
    
    async def _extract_district_info(self, article, detailed_record: DetailedVoterRecord):
        """Extract district information"""
        try:
            # Congressional District
            cong_elem = article.locator('span[id*="lblCDName"]')
            if await cong_elem.count() > 0:
                detailed_record.congressional_district = await cong_elem.inner_text()
                
            # Senate District
            senate_elem = article.locator('span[id*="lblSDName"]')
            if await senate_elem.count() > 0:
                detailed_record.senate_district = await senate_elem.inner_text()
                
            # Legislative District
            leg_elem = article.locator('span[id*="lblLDName"]')
            if await leg_elem.count() > 0:
                detailed_record.legislative_district = await leg_elem.inner_text()
                
            # Jurisdiction
            jurisdiction_elem = article.locator('span[id*="lblCountyName"]')
            if await jurisdiction_elem.count() > 0:
                detailed_record.jurisdiction = await jurisdiction_elem.inner_text()
                
            # Precinct
            precinct_elem = article.locator('span[id*="lblPrecinct"]').first
            if await precinct_elem.count() > 0:
                detailed_record.precinct = await precinct_elem.inner_text()
                
            # Precinct Number
            precinct_num_elem = article.locator('span[id*="lblPrecinctNumber"]')
            if await precinct_num_elem.count() > 0:
                detailed_record.precinct_number = await precinct_num_elem.inner_text()
                
            # Custom Districts
            custom_districts = []
            custom_district_elems = article.locator('span[id*="lblCustomDistrict"]')
            custom_count = await custom_district_elems.count()
            
            for i in range(custom_count):
                custom_elem = custom_district_elems.nth(i)
                district_text = await custom_elem.inner_text()
                if district_text:
                    custom_districts.append(district_text)
            
            if custom_districts:
                detailed_record.custom_districts = custom_districts
                
        except Exception as e:
            if self.debug:
                print(f"  Warning: Error extracting district info: {e}")
    
    async def _extract_vote_history(self, article, detailed_record: DetailedVoterRecord):
        """Extract voting history information"""
        try:
            # Early vote date
            early_vote_elem = article.locator('h6:has-text("Early Vote Date") + *').first
            if await early_vote_elem.count() > 0:
                detailed_record.early_vote_date = await early_vote_elem.inner_text()
                
            # TODO: Extract vote history table - this is complex and would need special handling
            
        except Exception as e:
            if self.debug:
                print(f"  Warning: Error extracting vote history: {e}")
    
    async def _extract_voter_frequency(self, article, detailed_record: DetailedVoterRecord):
        """Extract voter frequency scores"""
        try:
            # Voter Regularity General
            gen_reg_elem = article.locator('h6:has-text("Voter Regularity General") + *').first
            if await gen_reg_elem.count() > 0:
                detailed_record.voter_regularity_general = await gen_reg_elem.inner_text()
                
            # Voter Regularity Primary
            prim_reg_elem = article.locator('h6:has-text("Voter Regularity Primary") + *').first
            if await prim_reg_elem.count() > 0:
                detailed_record.voter_regularity_primary = await prim_reg_elem.inner_text()
                
        except Exception as e:
            if self.debug:
                print(f"  Warning: Error extracting voter frequency: {e}")
    
    async def _extract_geographical_info(self, article, detailed_record: DetailedVoterRecord):
        """Extract geographical information"""
        try:
            # DMA
            dma_elem = article.locator('h6:has-text("DMA") + *').first
            if await dma_elem.count() > 0:
                detailed_record.dma = await dma_elem.inner_text()
                
            # Census Block
            census_elem = article.locator('h6:has-text("Census Block") + *').first
            if await census_elem.count() > 0:
                detailed_record.census_block = await census_elem.inner_text()
                
            # Turf
            turf_elem = article.locator('h6:has-text("Turf") + *').first
            if await turf_elem.count() > 0:
                turf_text = await turf_elem.inner_text()
                if turf_text != "No Data Provided":
                    detailed_record.turf = turf_text
                    
        except Exception as e:
            if self.debug:
                print(f"  Warning: Error extracting geographical info: {e}")
    
    async def _extract_tags(self, article, detailed_record: DetailedVoterRecord):
        """Extract tags information"""
        try:
            # Extract tag names from tables
            tags = []
            tag_cells = article.locator('table tbody tr td:last-child')
            tag_count = await tag_cells.count()
            
            for i in range(tag_count):
                tag_cell = tag_cells.nth(i)
                tag_text = await tag_cell.inner_text()
                if tag_text and tag_text.strip():
                    tags.append(tag_text.strip())
            
            if tags:
                detailed_record.tags = tags
                
        except Exception as e:
            if self.debug:
                print(f"  Warning: Error extracting tags: {e}")
    
    async def _extract_notes(self, article, detailed_record: DetailedVoterRecord):
        """Extract notes information"""
        try:
            # Notes are in a list format - extract text from list items
            notes = []
            note_items = article.locator('li')
            note_count = await note_items.count()
            
            for i in range(note_count):
                note_item = note_items.nth(i)
                note_text = await note_item.inner_text()
                if note_text and note_text.strip():
                    notes.append(note_text.strip())
            
            if notes:
                detailed_record.notes = notes
                
        except Exception as e:
            if self.debug:
                print(f"  Warning: Error extracting notes: {e}")
    
    async def _extract_generic_info(self, article, detailed_record: DetailedVoterRecord):
        """Extract information from unknown article types using generic patterns"""
        try:
            article_text = await article.inner_text()
            
            # Look for common patterns like "Label: Value"  or "Label\nValue"
            import re
            
            # Pattern 1: Label: Value (on same line or next line)
            label_value_patterns = [
                r'([A-Za-z\s]+):\s*([^\n\r]+)',  # Label: Value
                r'([A-Za-z\s]+)\n([^\n\r]+)',    # Label\nValue
            ]
            
            for pattern in label_value_patterns:
                matches = re.findall(pattern, article_text, re.MULTILINE)
                for label, value in matches:
                    label = label.strip()
                    value = value.strip()
                    
                    if value and len(value) > 0 and value.lower() not in ['', 'n/a', 'none', 'null']:
                        # Map common labels to DetailedVoterRecord fields
                        label_lower = label.lower()
                        
                        if 'first name' in label_lower and not detailed_record.first_name:
                            detailed_record.first_name = value
                        elif 'middle name' in label_lower and not detailed_record.middle_name:
                            detailed_record.middle_name = value
                        elif 'last name' in label_lower and not detailed_record.last_name:
                            detailed_record.last_name = value
                        elif 'email' in label_lower and not detailed_record.email:
                            detailed_record.email = value
                        elif 'phone' in label_lower and 'home' in label_lower and not detailed_record.home_phone:
                            detailed_record.home_phone = value
                        elif 'phone' in label_lower and 'work' in label_lower and not detailed_record.work_phone:
                            detailed_record.work_phone = value
                        elif 'phone' in label_lower and 'cell' in label_lower and not detailed_record.cell_phone:
                            detailed_record.cell_phone = value
                        elif 'address' in label_lower and not detailed_record.address:
                            detailed_record.address = value
                        elif 'city' in label_lower and not detailed_record.city:
                            detailed_record.city = value
                        elif 'state' in label_lower and not detailed_record.state:
                            detailed_record.state = value
                        elif 'zip' in label_lower and not detailed_record.zip:
                            detailed_record.zip = value
                        elif 'party' in label_lower and not detailed_record.party_affiliation:
                            detailed_record.party_affiliation = value
                        elif 'precinct' in label_lower and not detailed_record.precinct:
                            detailed_record.precinct = value
                        elif 'voter id' in label_lower and not detailed_record.voter_id:
                            detailed_record.voter_id = value
                        elif 'registration' in label_lower and 'date' in label_lower and not detailed_record.registration_date:
                            detailed_record.registration_date = value
                        elif 'birthday' in label_lower or 'birth' in label_lower and not detailed_record.birthday:
                            detailed_record.birthday = value
                        elif 'gender' in label_lower and not detailed_record.gender:
                            detailed_record.gender = value
                        elif 'employer' in label_lower and not detailed_record.employer:
                            detailed_record.employer = value
                        elif 'occupation' in label_lower and not detailed_record.occupation:
                            detailed_record.occupation = value
                        
                        if self.debug:
                            print(f"      Generic extraction: {label} = {value}")
                            
        except Exception as e:
            if self.debug:
                print(f"  Warning: Error in generic extraction: {e}")
        
    async def search_voters(self, voter_names: List[str], **search_params) -> Dict[str, List[Dict[str, Any]]]:
        """Search for multiple voters"""
        # Get credentials
        if not self.credential_manager.check_credentials():
            username, password = self.credential_manager.prompt_credentials()
            self.credential_manager.save_credentials(username, password)
        else:
            username, password = self.credential_manager.load_credentials()
            
        all_results = {}
        
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=self.headless)
            except PlaywrightError as e:
                if "Executable doesn't exist" in str(e):
                    print("\nPlaywright browsers not found. Installing now...")
                    self._check_and_install_browsers()
                    # Try again after installation
                    browser = await p.chromium.launch(headless=self.headless)
                else:
                    raise
                    
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Navigate to site
                if self.debug:
                    print(f"Navigating to: {self.base_url}")
                await page.goto(self.base_url)
                
                # Authenticate
                if self.debug:
                    print("Authenticating...")
                if not await self._authenticate(page, username, password):
                    raise Exception("Authentication failed")
                    
                # Search for each voter
                for voter_name in voter_names:
                    print(f"\nSearching for: {voter_name}")
                    results = await self._search_voter(page, voter_name, **search_params)
                    all_results[voter_name] = results
                    print(f"Found {len(results)} result(s)")
                    
                    # Brief delay between searches
                    if voter_name != voter_names[-1]:
                        await page.wait_for_timeout(1000)
                
                # Debug mode: keep browser open
                if self.debug:
                    print("\n⚠️  Debug mode: Browser will remain open")
                    print("Press Enter to close the browser and exit...")
                    input()
                        
            finally:
                await browser.close()
                
        return all_results
        
    async def search_single_voter(self, page: Page, voter_name: str, **search_params) -> List[Dict[str, Any]]:
        """Search for a single voter using an existing authenticated page"""
        if self.debug:
            print(f"Searching for: {voter_name}")
            
        try:
            results = await self._search_voter(page, voter_name, **search_params)
            if self.debug:
                print(f"Found {len(results)} result(s)")
            return results
        except Exception as e:
            print(f"❌ Error searching for {voter_name}: {e}")
            return []
        
    def export_results(self, results: Dict[str, List[Dict[str, Any]]], format: str = "json", filename: Optional[str] = None):
        """Export results to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"voter_results_{timestamp}.{format}"
            
        if format == "json":
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2)
        elif format == "csv":
            with open(filename, 'w', newline='') as f:
                if results:
                    # Get all unique fields
                    all_fields = set()
                    for voter_results in results.values():
                        for record in voter_results:
                            all_fields.update(record.keys())
                    
                    writer = csv.DictWriter(f, fieldnames=['search_name'] + sorted(all_fields))
                    writer.writeheader()
                    
                    for search_name, voter_results in results.items():
                        for record in voter_results:
                            record['search_name'] = search_name
                            writer.writerow(record)
                            
        print(f"✓ Results exported to {filename}")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="GOP Data Center Voter Lookup")
    parser.add_argument("voters", nargs="*", help="Voter names to search (not required with --sheets)")
    parser.add_argument("--debug", action="store_true", help="Debug mode: shows browser and keeps it open")
    parser.add_argument("--export", choices=["json", "csv"], help="Export format")
    parser.add_argument("--output", help="Output filename")
    parser.add_argument("--delete-credentials", action="store_true", help="Delete stored credentials")
    
    # Search filters
    parser.add_argument("--address", help="Filter by address")
    parser.add_argument("--city", help="Filter by city")
    parser.add_argument("--zip", dest="zip_code", help="Filter by zip code")
    parser.add_argument("--phone", help="Filter by phone")
    parser.add_argument("--voter-id", help="Filter by voter ID")
    parser.add_argument("--extract-details", action="store_true", help="Extract detailed voter information (slower)")
    
    # Google Sheets integration
    parser.add_argument("--sheets", action="store_true", help="Use Google Sheets integration")
    parser.add_argument("--spreadsheet-id", help="Google Sheets spreadsheet ID")
    parser.add_argument("--sheet-name", default="Sheet1", help="Sheet name within spreadsheet")
    parser.add_argument("--name-column", default="A", help="Column containing voter names (e.g., 'A', 'B')")
    parser.add_argument("--start-row", type=int, default=2, help="Row to start reading names from")
    parser.add_argument("--results-start-column", help="Column to start adding voter data (required with --sheets)")
    parser.add_argument("--row-limit", type=int, help="Limit number of voter lookups (skips empty rows)")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.sheets and not args.voters:
        parser.error("Either provide voter names as arguments OR use --sheets for Google Sheets integration")
    
    if args.sheets and args.voters:
        print("⚠️  Warning: Voter names provided on command line will be ignored when using --sheets")
    
    # Set headless mode - default is True, False only in debug mode
    headless = not args.debug
    if args.debug:
        print("⚠️  Debug mode enabled - browser will be visible")
    
    # Check and install Playwright browsers if needed (before creating lookup instance)
    GOPVoterLookup._check_and_install_browsers()
    
    lookup = GOPVoterLookup(headless=headless, debug=args.debug, extract_details=args.extract_details)
    
    if args.delete_credentials:
        lookup.credential_manager.delete_credentials()
        return
        
    # Build search parameters
    search_params = {}
    for param in ['address', 'city', 'zip_code', 'phone', 'voter_id']:
        if getattr(args, param, None):
            search_params[param] = getattr(args, param)
    
    # Handle Google Sheets integration
    if args.sheets:
        if not args.spreadsheet_id:
            print("❌ --spreadsheet-id is required when using --sheets")
            return
            
        if not args.results_start_column:
            print("❌ --results-start-column is required when using --sheets")
            print("   Example: --results-start-column C (to start adding data from column C)")
            return
            
        sheets_manager = GoogleSheetsManager(Path.cwd(), debug=args.debug)
        
        if not sheets_manager.authenticate():
            print("❌ Failed to authenticate with Google Sheets")
            return
            
        # Get spreadsheet info
        sheet_info = sheets_manager.get_spreadsheet_info(args.spreadsheet_id)
        if not sheet_info:
            print("❌ Failed to access spreadsheet")
            return
            
        print(f"📊 Working with spreadsheet: {sheet_info['title']}")
        print(f"📋 Available sheets: {', '.join(sheet_info['sheets'])}")
        
        if args.sheet_name not in sheet_info['sheets']:
            print(f"❌ Sheet '{args.sheet_name}' not found")
            return
            
        # Read names from the specified column
        name_entries = sheets_manager.read_column(
            args.spreadsheet_id, 
            args.sheet_name, 
            args.name_column, 
            args.start_row,
            args.row_limit
        )
        
        if not name_entries:
            print("❌ No valid names found in the specified column")
            return
            
        print(f"📝 Found {len(name_entries)} valid names in spreadsheet")
        if args.row_limit:
            print(f"🔢 Will process up to {args.row_limit} rows (including already processed ones)")
            
        # Extract just the names for the lookup
        names = [entry['name'] for entry in name_entries]
        
        # Generate column mapping starting from the specified column
        column_mapping, fields_order = sheets_manager.generate_column_mapping(
            args.results_start_column, 
            args.extract_details
        )
        
        print(f"📋 Data will be added starting from column {args.results_start_column}:")
        for i, field in enumerate(fields_order):
            column = column_mapping[field]
            print(f"   {column}: {field.replace('_', ' ').title()}")
            
        # Optionally write headers to the spreadsheet
        if args.start_row > 1:  # Only if there's a header row
            headers = [field.replace('_', ' ').title() for field in fields_order]
            header_range = f"{args.sheet_name}!{args.results_start_column}1"
            
            # Create column range for headers (e.g., "C1:J1")
            end_column = sheets_manager.column_number_to_letter(
                sheets_manager.column_letter_to_number(args.results_start_column) + len(fields_order) - 1
            )
            header_range = f"{args.sheet_name}!{args.results_start_column}1:{end_column}1"
            
            try:
                sheets_manager.service.spreadsheets().values().update(
                    spreadsheetId=args.spreadsheet_id,
                    range=header_range,
                    valueInputOption='RAW',
                    body={'values': [headers]}
                ).execute()
                print(f"✅ Added headers to row 1")
            except Exception as e:
                if args.debug:
                    print(f"⚠️  Could not add headers: {e}")
        
        # Process voters individually - search then immediately update
        print(f"🔄 Processing {len(name_entries)} voters individually...")
        
        # Get GOP credentials for authentication
        if not lookup.credential_manager.check_credentials():
            username, password = lookup.credential_manager.prompt_credentials()
            lookup.credential_manager.save_credentials(username, password)
        else:
            username, password = lookup.credential_manager.load_credentials()
        
        updated_count = 0
        
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=lookup.headless)
            except Exception as e:
                if "Executable doesn't exist" in str(e):
                    print("\nPlaywright browsers not found. Installing now...")
                    lookup._check_and_install_browsers()
                    browser = await p.chromium.launch(headless=lookup.headless)
                else:
                    raise
                    
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Navigate and authenticate once
                if args.debug:
                    print(f"Navigating to: {lookup.base_url}")
                await page.goto(lookup.base_url)
                
                if args.debug:
                    print("Authenticating...")
                if not await lookup._authenticate(page, username, password):
                    print("❌ Authentication failed")
                    return
                
                # Process each voter individually
                skipped_count = 0
                processed_count = 0
                
                for entry_idx, name_entry in enumerate(name_entries):
                    voter_name = name_entry['name']
                    current_row = name_entry['row']
                    
                    print(f"\n[{entry_idx + 1}/{len(name_entries)}] Processing: {voter_name} (row {current_row})")
                    
                    # Check if this row already has data (indicating it's been processed)
                    if sheets_manager.check_row_already_processed(
                        args.spreadsheet_id,
                        args.sheet_name,
                        current_row,
                        args.results_start_column
                    ):
                        print(f"  ⏭️  Skipped - already processed")
                        skipped_count += 1
                        # Important: Count this toward the processed total for row limit
                        processed_count += 1
                        
                        # Check if we've reached the row limit
                        if args.row_limit and processed_count >= args.row_limit:
                            print(f"\n🔢 Reached row limit of {args.row_limit}")
                            break
                        continue
                    
                    # Search for this voter
                    voter_results = await lookup.search_single_voter(page, voter_name, **search_params)
                    
                    if voter_results:
                        # Use the first result if multiple found
                        voter_data = voter_results[0]
                        
                        # If extract_details is enabled and detailed_info exists, merge it into voter_data
                        if args.extract_details and 'detailed_info' in voter_data and voter_data['detailed_info']:
                            # Merge detailed_info fields into the main voter_data dictionary
                            detailed_info = voter_data.pop('detailed_info')
                            voter_data.update(detailed_info)
                            
                        if args.debug:
                            print(f"  Available fields in voter_data: {list(voter_data.keys())}")
                        
                        # Immediately update the spreadsheet row
                        if sheets_manager.update_row(
                            args.spreadsheet_id,
                            args.sheet_name,
                            current_row,
                            voter_data,
                            column_mapping
                        ):
                            updated_count += 1
                            print(f"  ✅ Updated row {current_row}")
                        else:
                            print(f"  ❌ Failed to update row {current_row}")
                    else:
                        print(f"  ⚠️  No results found")
                    
                    # Increment processed count
                    processed_count += 1
                    
                    # Check if we've reached the row limit
                    if args.row_limit and processed_count >= args.row_limit:
                        print(f"\n🔢 Reached row limit of {args.row_limit}")
                        break
                    
                    # Brief delay between searches
                    if entry_idx < len(name_entries) - 1:
                        await page.wait_for_timeout(1000)
                
                # Debug mode: keep browser open
                if args.debug:
                    print("\n⚠️  Debug mode: Browser will remain open")
                    print("Press Enter to close the browser and exit...")
                    input()
                        
            finally:
                await browser.close()
                
        print(f"\n🎉 Processing complete:")
        print(f"   ✅ Updated: {updated_count}")
        print(f"   ⏭️  Skipped (already processed): {skipped_count}")
        print(f"   📊 Total rows examined: {processed_count}")
        if args.row_limit:
            print(f"   🔢 Row limit applied: {args.row_limit}")
        return
    
    # Standard command line mode
    # Perform searches
    results = await lookup.search_voters(args.voters, **search_params)
    
    # Display results
    for voter_name, voter_results in results.items():
        print(f"\n=== Results for {voter_name} ===")
        for i, record in enumerate(voter_results, 1):
            print(f"\nResult {i}:")
            # Display basic voter info first
            for key, value in record.items():
                if key != 'detailed_info' and value:
                    if key == 'view_voter_url':
                        print(f"  📄 View Full Details: {value}")
                    else:
                        print(f"  {key}: {value}")
            
            # Display detailed info if available
            if 'detailed_info' in record and record['detailed_info']:
                print(f"\n  --- Detailed Information ---")
                detailed = record['detailed_info']
                
                # Group fields by category for better readability
                categories = {
                    'Personal': ['first_name', 'middle_name', 'last_name', 'birthday', 'age', 'gender'],
                    'Contact': ['mobile_phone', 'mobile_phone_reliability', 'landline_phone', 'landline_phone_reliability', 
                               'primary_address', 'secondary_address', 'facebook', 'instagram', 'twitter'],
                    'Voter Info': ['registration_status', 'registration_date', 'last_activity_date', 
                                  'official_party', 'observed_party', 'calculated_party', 'absentee_status'],
                    'Ethnicity': ['state_reported_ethnicity', 'modeled_ethnicity', 'observed_ethnicity'],
                    'Identification': ['gopdc_voter_key', 'rnc_client_id', 'state_voter_id', 
                                      'jurisdictional_voter_id', 'rnc_registration_id'],
                    'Districts': ['congressional_district', 'senate_district', 'legislative_district', 
                                 'jurisdiction', 'precinct', 'precinct_number', 'custom_districts'],
                    'Vote History': ['early_vote_date', 'vote_history'],
                    'Voter Frequency': ['overall_frequency', 'general_frequency', 'primary_frequency', 
                                       'voter_regularity_general', 'voter_regularity_primary'],
                    'Geographic': ['dma', 'census_block', 'turf'],
                    'Additional': ['tags', 'notes']
                }
                
                for category, fields in categories.items():
                    category_items = []
                    for field in fields:
                        if field in detailed and detailed[field]:
                            value = detailed[field]
                            if isinstance(value, list):
                                category_items.append(f"    {field}: {', '.join(str(v) for v in value)}")
                            else:
                                category_items.append(f"    {field}: {value}")
                    
                    # Display category if it has any items
                    if category_items:
                        print(f"\n  {category}:")
                        for item in category_items:
                            print(item)
                
                # Display any remaining fields not categorized
                categorized_fields = set()
                for fields in categories.values():
                    categorized_fields.update(fields)
                
                other_items = []
                for key, value in detailed.items():
                    if key not in categorized_fields and value:
                        if isinstance(value, list):
                            other_items.append(f"    {key}: {', '.join(str(v) for v in value)}")
                        else:
                            other_items.append(f"    {key}: {value}")
                
                if other_items:
                    print(f"\n  Other:")
                    for item in other_items:
                        print(item)
                    
    # Export if requested
    if args.export:
        lookup.export_results(results, format=args.export, filename=args.output)


if __name__ == "__main__":
    asyncio.run(main())