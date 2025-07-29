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


@dataclass
class VoterRecord:
    """Structure for voter information"""
    name: str
    address: str
    city: str
    state: str
    zip_code: str
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    calculated_party: Optional[str] = None
    voter_id: Optional[str] = None
    precinct: Optional[str] = None
    status: Optional[str] = None
    

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
    
    def __init__(self, headless: bool = True, debug: bool = False):
        self.headless = headless
        self.debug = debug
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
                        calculated_party=party
                    )
                    
                    results.append(asdict(record))
                    
            except Exception as e:
                print(f"Warning: Error parsing row {i}: {e}")
                continue
                
        return results
        
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
    parser.add_argument("voters", nargs="+", help="Voter names to search")
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
    
    args = parser.parse_args()
    
    # Set headless mode - default is True, False only in debug mode
    headless = not args.debug
    if args.debug:
        print("⚠️  Debug mode enabled - browser will be visible")
    
    # Check and install Playwright browsers if needed (before creating lookup instance)
    GOPVoterLookup._check_and_install_browsers()
    
    lookup = GOPVoterLookup(headless=headless, debug=args.debug)
    
    if args.delete_credentials:
        lookup.credential_manager.delete_credentials()
        return
        
    # Build search parameters
    search_params = {}
    for param in ['address', 'city', 'zip_code', 'phone', 'voter_id']:
        if getattr(args, param, None):
            search_params[param] = getattr(args, param)
    
    # Perform searches
    results = await lookup.search_voters(args.voters, **search_params)
    
    # Display results
    for voter_name, voter_results in results.items():
        print(f"\n=== Results for {voter_name} ===")
        for i, record in enumerate(voter_results, 1):
            print(f"\nResult {i}:")
            for key, value in record.items():
                if value:
                    print(f"  {key}: {value}")
                    
    # Export if requested
    if args.export:
        lookup.export_results(results, format=args.export, filename=args.output)


if __name__ == "__main__":
    asyncio.run(main())