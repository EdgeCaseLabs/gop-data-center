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
        """Extract detailed voter information by clicking View Voter button for a specific row"""
        try:
            if self.debug:
                print(f"    Attempting to extract detailed info for row {row_index}")
                
            # Look for View Voter button/link in this row
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
                
            # Get the current number of pages before clicking
            initial_pages = len(page.context.pages)
            
            # Click the View Voter button
            if self.debug:
                print(f"      Clicking View Voter button...")
            await view_voter_button.click()
            
            # Wait for new page/tab to open or current page to navigate
            await page.wait_for_timeout(2000)  # Give time for navigation/new tab
            
            current_pages = len(page.context.pages)
            detail_page = None
            
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
            
            # Extract detailed information
            detailed_record = await self._extract_detailed_voter_info(detail_page)
            
            # Close the new tab if one was opened, or navigate back if current page was used
            if current_pages > initial_pages:
                # New tab was opened, close it
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
            articles = page.locator('article')
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
            
            # Determine article type based on content
            if "Personal Info" in article_text:
                await self._extract_personal_info(article, detailed_record)
            elif "Contact Info" in article_text:
                await self._extract_contact_info(article, detailed_record)
            elif "Voter Info" in article_text:
                await self._extract_voter_info(article, detailed_record)
            elif "Voter Identification" in article_text:
                await self._extract_voter_identification(article, detailed_record)
            elif "District Info" in article_text:
                await self._extract_district_info(article, detailed_record)
            elif "Vote History" in article_text:
                await self._extract_vote_history(article, detailed_record)
            elif "Voter Frequency" in article_text:
                await self._extract_voter_frequency(article, detailed_record)
            elif "Geographical Location" in article_text:
                await self._extract_geographical_info(article, detailed_record)
            elif "Tags" in article_text:
                if self.debug:
                    print(f"    Skipping Tags section as requested")
                # Skip tags as they're not useful
            elif "Notes" in article_text:
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
            # Extract name components
            first_name_elem = article.locator('h6:has-text("First Name") + *')
            if await first_name_elem.count() > 0:
                detailed_record.first_name = await first_name_elem.first.inner_text()
                
            middle_name_elem = article.locator('h6:has-text("Middle Name") + *')
            if await middle_name_elem.count() > 0:
                detailed_record.middle_name = await middle_name_elem.first.inner_text()
                
            last_name_elem = article.locator('h6:has-text("Last Name") + *')
            if await last_name_elem.count() > 0:
                detailed_record.last_name = await last_name_elem.first.inner_text()
                
            # Construct full name
            if detailed_record.first_name or detailed_record.last_name:
                name_parts = [p for p in [detailed_record.first_name, detailed_record.middle_name, detailed_record.last_name] if p]
                detailed_record.name = " ".join(name_parts)
            
            # Extract birthday
            birthday_elem = article.locator('h6:has-text("Birthday") + *')
            if await birthday_elem.count() > 0:
                detailed_record.birthday = await birthday_elem.first.inner_text()
            
            # Extract age  
            age_elem = article.locator('h6:has-text("Age") + *')
            if await age_elem.count() > 0:
                detailed_record.age = await age_elem.first.inner_text()
                
            # Extract gender
            gender_elem = article.locator('h6:has-text("Gender") + *')
            if await gender_elem.count() > 0:
                detailed_record.gender = await gender_elem.first.inner_text()
                
        except Exception as e:
            if self.debug:
                print(f"  Warning: Error extracting personal info: {e}")
    
    async def _extract_contact_info(self, article, detailed_record: DetailedVoterRecord):
        """Extract contact information from Contact Info article"""
        try:
            # Extract mobile phone
            mobile_elem = article.locator('h6:has-text("Mobile Phone") + *').first
            if await mobile_elem.count() > 0:
                detailed_record.mobile_phone = await mobile_elem.inner_text()
                
            # Extract mobile phone TRC
            mobile_trc_elem = article.locator('h6:has-text("TRC") + *').first
            if await mobile_trc_elem.count() > 0:
                detailed_record.mobile_phone_reliability = await mobile_trc_elem.inner_text()
            
            # Extract landline phone
            landline_elem = article.locator('h6:has-text("Landline Phone") + *').first
            if await landline_elem.count() > 0:
                detailed_record.landline_phone = await landline_elem.inner_text()
            
            # Extract primary address
            primary_addr_elem = article.locator('h6:has-text("Primary Address") + *').first
            if await primary_addr_elem.count() > 0:
                addr_text = await primary_addr_elem.inner_text()
                # Get the next sibling for the full address
                next_elem = article.locator('h6:has-text("Primary Address")').locator('..').locator('*').nth(1)
                if await next_elem.count() > 0:
                    addr_line2 = await next_elem.inner_text()
                    detailed_record.primary_address = f"{addr_text}, {addr_line2}"
                else:
                    detailed_record.primary_address = addr_text
                    
            # Extract secondary address  
            secondary_addr_elem = article.locator('h6:has-text("Secondary Address") + *').first
            if await secondary_addr_elem.count() > 0:
                addr_text = await secondary_addr_elem.inner_text()
                next_elem = article.locator('h6:has-text("Secondary Address")').locator('..').locator('*').nth(1)
                if await next_elem.count() > 0:
                    addr_line2 = await next_elem.inner_text()
                    detailed_record.secondary_address = f"{addr_text}, {addr_line2}"
                else:
                    detailed_record.secondary_address = addr_text
            
            # Extract social media (if not "No Data Provided")
            facebook_elem = article.locator('h6:has-text("Facebook") + *').first
            if await facebook_elem.count() > 0:
                fb_text = await facebook_elem.inner_text()
                if fb_text != "No Data Provided":
                    detailed_record.facebook = fb_text
                    
            instagram_elem = article.locator('h6:has-text("Instagram") + *').first
            if await instagram_elem.count() > 0:
                ig_text = await instagram_elem.inner_text()
                if ig_text != "No Data Provided":
                    detailed_record.instagram = ig_text
                    
            twitter_elem = article.locator('h6:has-text("Twitter") + *').first
            if await twitter_elem.count() > 0:
                tw_text = await twitter_elem.inner_text()
                if tw_text != "No Data Provided":
                    detailed_record.twitter = tw_text
                    
        except Exception as e:
            if self.debug:
                print(f"  Warning: Error extracting contact info: {e}")
    
    async def _extract_voter_info(self, article, detailed_record: DetailedVoterRecord):
        """Extract voter registration information"""
        try:
            # Registration status
            reg_status_elem = article.locator('h6:has-text("Registration Status") + *').first
            if await reg_status_elem.count() > 0:
                detailed_record.registration_status = await reg_status_elem.inner_text()
            
            # Registration date
            reg_date_elem = article.locator('h6:has-text("Registration Date") + *').first
            if await reg_date_elem.count() > 0:
                detailed_record.registration_date = await reg_date_elem.inner_text()
                
            # Official party
            official_party_elem = article.locator('h6:has-text("Official Party") + *').first
            if await official_party_elem.count() > 0:
                detailed_record.official_party = await official_party_elem.inner_text()
                
            # Observed party
            observed_party_elem = article.locator('h6:has-text("Observed Party") + *').first
            if await observed_party_elem.count() > 0:
                detailed_record.observed_party = await observed_party_elem.inner_text()
                
            # Calculated party
            calc_party_elem = article.locator('h6:has-text("Calculated Party") + *').first
            if await calc_party_elem.count() > 0:
                detailed_record.calculated_party = await calc_party_elem.inner_text()
                
            # Modeled ethnicity
            modeled_eth_elem = article.locator('h6:has-text("Modeled Ethnicity") + *').first
            if await modeled_eth_elem.count() > 0:
                detailed_record.modeled_ethnicity = await modeled_eth_elem.inner_text()
                
        except Exception as e:
            if self.debug:
                print(f"  Warning: Error extracting voter info: {e}")
    
    async def _extract_voter_identification(self, article, detailed_record: DetailedVoterRecord):
        """Extract voter ID numbers"""
        try:
            # GOPDC Voter Key
            gopdc_elem = article.locator('h6:has-text("GOPDC Voter Key") + *').first
            if await gopdc_elem.count() > 0:
                detailed_record.gopdc_voter_key = await gopdc_elem.inner_text()
                
            # RNC Client ID
            rnc_elem = article.locator('h6:has-text("RNC Client ID") + *').first
            if await rnc_elem.count() > 0:
                detailed_record.rnc_client_id = await rnc_elem.inner_text()
                
            # State Voter ID
            state_elem = article.locator('h6:has-text("State Voter ID") + *').first
            if await state_elem.count() > 0:
                detailed_record.state_voter_id = await state_elem.inner_text()
                
        except Exception as e:
            if self.debug:
                print(f"  Warning: Error extracting voter identification: {e}")
    
    async def _extract_district_info(self, article, detailed_record: DetailedVoterRecord):
        """Extract district information"""
        try:
            # Congressional District
            cong_elem = article.locator('h6:has-text("Congressional District") + *').first
            if await cong_elem.count() > 0:
                detailed_record.congressional_district = await cong_elem.inner_text()
                
            # Senate District
            senate_elem = article.locator('h6:has-text("Senate District") + *').first
            if await senate_elem.count() > 0:
                detailed_record.senate_district = await senate_elem.inner_text()
                
            # Legislative District
            leg_elem = article.locator('h6:has-text("Legislative District") + *').first
            if await leg_elem.count() > 0:
                detailed_record.legislative_district = await leg_elem.inner_text()
                
            # Precinct
            precinct_elem = article.locator('h6:has-text("Precinct") + *').first
            if await precinct_elem.count() > 0:
                detailed_record.precinct = await precinct_elem.inner_text()
                
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
    parser.add_argument("--extract-details", action="store_true", help="Extract detailed voter information (slower)")
    
    args = parser.parse_args()
    
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
                    'Personal': ['first_name', 'middle_name', 'last_name', 'suffix', 'gender', 'birthday', 'age'],
                    'Contact': ['email', 'home_phone', 'work_phone', 'cell_phone', 'fax'],
                    'Address': ['address', 'apartment', 'city', 'state', 'zip', 'county', 'neighborhood'],
                    'Voter Info': ['voter_id', 'registration_date', 'voter_status', 'party_affiliation', 'precinct'],
                    'Districts': ['district_congress', 'district_state_house', 'district_state_senate', 'district_judicial', 'district_school', 'district_city', 'district_county'],
                    'History': ['primary_votes', 'general_votes', 'vote_history'],
                    'Additional': ['employer', 'occupation', 'spouse_name', 'notes']
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