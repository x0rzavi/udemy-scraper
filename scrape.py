import csv
import math
import os
import re
import sys
from typing import Dict, List, Tuple

from bs4 import BeautifulSoup
from seleniumbase import SB


class UdemyScraper:
    """Scraper for Udemy courses to extract course information."""

    def __init__(self, email: str, password: str, account_name: str):
        """Initialize the scraper with user credentials.

        Args:
            email: User's email address
            password: User's password
            account_name: Account first name for verification
        """
        self.email = email
        self.password = password
        self.account_name = account_name

        # Create saved_cookies directory if it doesn't exist
        self.cookies_dir = "saved_cookies"
        os.makedirs(self.cookies_dir, exist_ok=True)
        self.cookies_file = os.path.join(self.cookies_dir, "cookies.txt")

        self.courses_file = "courses_details.csv"
        self.formatted_courses_file = "courses_details_formatted.csv"

    def login(self, force: bool = False) -> bool:
        """Authenticate with Udemy.

        Args:
            force: If True, ignore existing cookies and force new login

        Returns:
            bool: True if login was successful, False otherwise
        """
        with SB(uc=True, test=True, locale_code="en") as sb:
            login_url = "https://www.udemy.com/join/passwordless-auth/?locale=en_US&next=https%3A%2F%2Fwww.udemy.com%2F&response_type=html"
            login_selector = "#form-group--1"
            passwordless_button_selector_1 = (
                "button[type='submit']:contains('Continue with email')"
            )
            passwordless_button_selector_2 = "button[type='submit']:contains('Log in')"
            password_selector = "#form-group--3"
            passwordbased_button_selector = "#udemy > div.ud-main-content-wrapper > div.ud-main-content > div > main > div > div > div:nth-child(2) > form > button"

            try:
                sb.uc_open_with_reconnect(login_url, 5)  # open url bypassing captcha
                if not force and os.path.exists(
                    self.cookies_file
                ):  # use existing cookies if available
                    sb.load_cookies(self.cookies_file)
                    sb.refresh()
                    sb.assert_text_visible(self.account_name)
                    return True
                else:
                    raise Exception("Force login or no cookies available")
            except Exception:  # not logged in or forced login
                return self._perform_login(
                    sb,
                    login_url,
                    login_selector,
                    password_selector,
                    passwordless_button_selector_1,
                    passwordless_button_selector_2,
                    passwordbased_button_selector,
                )

    def _perform_login(
        self,
        sb,
        login_url,
        login_selector,
        password_selector,
        passwordless_button_selector_1,
        passwordless_button_selector_2,
        passwordbased_button_selector,
    ) -> bool:
        """Handle the actual login process.

        Returns:
            bool: True if login successful, False otherwise
        """
        max_attempts = 3
        current_attempt = 0

        while current_attempt < max_attempts:
            current_attempt += 1
            try:
                sb.uc_open_with_reconnect(login_url, 5)
                sb.get_element(login_selector, timeout=15).click()
                sb.type(login_selector, self.email)

                try:  # try passwordless login first
                    sb.get_element(passwordless_button_selector_1, timeout=15).click()
                    print(
                        "WARNING: ENTER LOGIN CODE FROM EMAIL AND WAIT 60s FOR AUTO CLICK!"
                    )
                    sb.wait(60)
                    sb.get_element(passwordless_button_selector_2, timeout=15).click()
                except Exception:  # fall back to password-based login
                    sb.get_element(password_selector, timeout=15).click()
                    sb.type(password_selector, self.password)
                    sb.get_element(passwordbased_button_selector, timeout=15).click()

                # Verify login success
                sb.assert_text_visible(self.account_name)
                sb.save_cookies(self.cookies_file)
                return True

            except Exception:
                print(
                    f"WARNING: LOGIN FAILED (Attempt {current_attempt}/{max_attempts})"
                )
                if current_attempt < max_attempts:
                    print("Waiting 60s before retrying...")
                    sb.wait(60)
                else:
                    print(f"ERROR: Failed to login after {max_attempts} attempts")
                    return False

    def scrape_courses(self) -> Dict[str, str]:
        """Scrape all user's enrolled courses.

        Returns:
            Dict mapping course titles to course duration
        """
        with SB(uc=True, test=True, locale_code="en") as sb:
            courses_url = "https://www.udemy.com/home/my-courses/learning/"

            # Selectors
            overview_selector = "//span[text()='Overview']"
            time_selector = "//div[contains(text(), 'Video:')]"
            pagination_selector = "div.pagination--pagination-label--tgma-"
            course_grid_selector = "div.my-courses__course-card-grid"

            # Load the courses page
            sb.uc_open_with_reconnect(courses_url, 5)
            sb.load_cookies(self.cookies_file)
            sb.refresh()
            sb.get_element(pagination_selector, timeout=15)

            # Get total number of courses and pages
            courses_list, courses_count, pages_count = self._get_course_metadata(sb)
            print(f"INFO: TOTAL COURSES: {courses_count}")

            # Get all course URLs from pagination
            courses_list = self._get_all_course_urls(
                sb, courses_url, course_grid_selector, pages_count
            )

            # Get existing courses to avoid re-scraping
            existing_courses = self._get_existing_courses()

            # Scrape details for each course
            courses_details = self._scrape_course_details(
                sb, courses_list, existing_courses, overview_selector, time_selector
            )

            print("INFO: SAVED COURSE DETAILS!")
            return courses_details

    def _get_course_metadata(self, sb) -> Tuple[List[str], int, int]:
        """Extract course count and pagination info.

        Returns:
            Tuple of (empty course list, course count, page count)
        """
        soup = BeautifulSoup(sb.get_page_source(), "lxml")
        courses_num_details = soup.select("div[class*='pagination-label']")[
            0
        ].text.strip()
        courses_num_match = re.search(r"of (\d+) courses", courses_num_details)
        courses_count = int(courses_num_match.group(1))
        pages_count = math.ceil(courses_count / 12)  # 12 courses per page
        return [], courses_count, pages_count

    def _get_all_course_urls(
        self, sb, courses_url: str, course_grid_selector: str, pages_count: int
    ) -> List[str]:
        """Get URLs for all courses from pagination.

        Returns:
            List of course URLs
        """
        courses_list = []

        # for page in range(1, pages_count + 1):
        for page in range(1, 2):
            sb.uc_open(f"{courses_url}?p={page}")
            sb.get_element(course_grid_selector, timeout=15)

            soup = BeautifulSoup(sb.get_page_source(), "lxml")
            course_elements = soup.find_all(
                "h3", attrs={"data-purpose": "course-title-url"}
            )

            for element in course_elements:
                course_link = element.find("a").get("href")
                courses_list.append(f"https://www.udemy.com{course_link}")

            print(f"INFO: PROCESSED PAGE #{page}/{pages_count}")

        return courses_list

    def _get_existing_courses(self) -> set:
        """Get set of courses that have already been scraped.

        Returns:
            Set of course URLs already in the CSV
        """
        existing_courses = set()
        try:
            with open(self.courses_file, "r", newline="", encoding="utf-8") as file:
                reader = csv.reader(file)
                next(reader, None)  # Skip header
                for row in reader:
                    if row:  # Ensure row is not empty
                        existing_courses.add(row[0])
        except FileNotFoundError:
            pass

        return existing_courses

    def _scrape_course_details(
        self,
        sb,
        courses_list: List[str],
        existing_courses: set,
        overview_selector: str,
        time_selector: str,
    ) -> Dict[str, str]:
        """Scrape details for each course.

        Returns:
            Dict mapping course titles to durations
        """
        courses_details = {}

        with open(self.courses_file, "a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)

            # Write header if file is new
            if not existing_courses:
                writer.writerow(["Course Link", "Course Title", "Course Time"])

            for index, course_url in enumerate(courses_list, 1):
                if course_url in existing_courses:
                    print(f"INFO: SKIPPED COURSE #{index} (EXISTING)")
                    continue

                try:
                    sb.uc_open(course_url)
                    sb.get_element(overview_selector, timeout=15).click()
                    # sb.wait(120)
                    sb.get_element(time_selector, timeout=2)

                    soup = BeautifulSoup(sb.get_page_source(), "lxml")

                    # Extract course title
                    course_title_element = soup.find("title")
                    course_title = (
                        course_title_element.text.strip()
                        .replace("Course: ", "")
                        .replace(" | Udemy", "")
                        if course_title_element
                        else "N/A"
                    )

                    # Extract course duration
                    course_time_element = soup.find(
                        "div", class_=re.compile("video-length")
                    ).find(class_="ud-heading-md")
                    course_time = (
                        course_time_element.text.strip()
                        if course_time_element
                        else "N/A"
                    )

                    # Save to CSV and dict
                    writer.writerow([course_url, course_title, course_time])
                    courses_details[course_title] = course_time
                    print(f"INFO: PROCESSED COURSE #{index} (NEW)")

                except Exception as e:
                    print(f"ERROR processing course {course_url}: {str(e)}")

        return courses_details

    def format_csv(self) -> None:
        """Format course durations from text to minutes."""
        if not os.path.exists(self.courses_file):
            print(f"ERROR: Input file {self.courses_file} not found")
            return

        with (
            open(self.courses_file, "r", newline="", encoding="utf-8") as input_file,
            open(
                self.formatted_courses_file, "w", newline="", encoding="utf-8"
            ) as output_file,
        ):
            reader = csv.reader(input_file)
            writer = csv.writer(output_file)

            # Copy and write headers
            try:
                headers = next(reader)
                writer.writerow(headers)

                total_minutes = 0
                course_count = 0

                for row in reader:
                    if not row:  # Skip empty rows
                        continue

                    if len(row) < 3:  # Ensure row has enough columns
                        print(f"WARNING: Skipping malformed row: {row}")
                        continue

                    # Skip rows containing "questions" in any column
                    if any("questions" in column.lower() for column in row):
                        continue

                    # Convert time to minutes
                    time_str = row[2]
                    minutes = self._convert_to_minutes(time_str)
                    row[2] = minutes
                    writer.writerow(row)

                    if minutes > 0:
                        total_minutes += minutes
                        course_count += 1

                if course_count > 0:
                    hours = total_minutes / 60
                    print(
                        f"INFO: Total course time: {hours:.1f} hours ({total_minutes} minutes)"
                    )
                    print(
                        f"INFO: Average course length: {(total_minutes / course_count):.1f} minutes"
                    )

                print("INFO: FORMATTED COURSE DETAILS!")

            except StopIteration:
                print("WARNING: Input file is empty")

    def _convert_to_minutes(self, time_str: str) -> int:
        """Convert time string to minutes.

        Args:
            time_str: String like "5 hours 30 mins" or "45 mins"

        Returns:
            Total minutes as integer
        """
        if time_str == "N/A":
            return 0

        total_minutes = 0
        hours_match = re.search(r"(\d+(?:\.\d+)?)\s*hours?", time_str)
        minutes_match = re.search(r"(\d+)\s*mins?", time_str)

        if hours_match:
            total_minutes += float(hours_match.group(1)) * 60
        if minutes_match:
            total_minutes += int(minutes_match.group(1))

        return int(total_minutes)


def main():
    """Main entry point for the script."""
    try:
        print("=== Udemy Course Scraper ===")
        # email = input("Enter email address: ")
        # password = input("Enter password: ")
        # account_name = input("Enter account first-name: ")
        email = "***REMOVED***"
        password = "***REMOVED***"
        account_name = "Avishek"

        scraper = UdemyScraper(email, password, account_name)

        # Attempt login
        if scraper.login(force=False):
            print("INFO: LOGGED IN SUCCESSFULLY!")

            # Scrape courses
            courses = scraper.scrape_courses()

            # Format CSV for analysis
            scraper.format_csv()

            print("INFO: SCRAPING COMPLETED SUCCESSFULLY!")
        else:
            print("ERROR: LOGIN UNSUCCESSFUL!")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nINFO: Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
