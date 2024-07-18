from seleniumbase import SB
from bs4 import BeautifulSoup
import re
import csv
import math


def checkLogin(email: str, password: str, account_name: str, force: bool) -> bool:
    with SB(uc=True, test=True, locale_code="en") as sb:
        login_url = "https://www.udemy.com/join/passwordless-auth/?locale=en_US&next=https%3A%2F%2Fwww.udemy.com%2F&response_type=html"
        login_selector = "#form-group--1"
        password_selector = "#form-group--3"
        passwordless_button_selector_1 = "#udemy > div.ud-main-content-wrapper > div.ud-main-content > div > div > main > div > div > form > button"
        passwordless_button_selector_2 = "#udemy > div.ud-main-content-wrapper > div.ud-main-content > div > div > main > div > div > div > div.auth-form-row--xx-large--8OECD > form > div.auth-form-row--small--Byo8R > button"
        passwordbased_button_selector = "#udemy > div.ud-main-content-wrapper > div.ud-main-content > div > main > div > div > div:nth-child(2) > form > button"

        try:
            sb.uc_open_with_reconnect(login_url, 5)  # open url bypassing captcha
            if not force:  # force change account
                sb.load_cookies("cookies.txt")
            sb.refresh()
            sb.assert_text_visible(account_name)
        except Exception:  # not logged in
            while True:
                sb.uc_open_with_reconnect(login_url, 5)  # open url bypassing captcha
                sb.get_element(login_selector).click()
                sb.type(login_selector, email)
                try:  # password less login
                    sb.get_element(passwordless_button_selector_1).click()
                    print(
                        "WARNING: ENTER LOGIN CODE FROM EMAIL AND WAIT FOR AUTO CLICK!"
                    )
                    sb.wait(60)
                    sb.get_element(passwordless_button_selector_2).click()
                except Exception:  # password based login
                    sb.get_element(password_selector).click()
                    sb.type(password_selector, password)
                    sb.get_element(passwordbased_button_selector).click()

                try:
                    sb.assert_text_visible(account_name)
                except Exception:
                    sb.wait(60)  # wait before retrying
                    continue
                else:
                    sb.save_cookies("cookies.txt")
                    return True
        else:  # logged in
            return True


def listCourses(wait_time: int) -> dict:
    with SB(uc=True, test=True, locale_code="en") as sb:
        courses_url = "https://www.udemy.com/home/my-courses/learning/"
        overview_selector = "#tabs--1-tab-2"
        sb.uc_open_with_reconnect(courses_url, 5)  # open url bypassing captcha
        sb.load_cookies("cookies.txt")
        sb.refresh()
        sb.wait(wait_time)

        soup = BeautifulSoup(sb.get_page_source(), "lxml")
        courses_num_details = soup.select("div[class*='pagination-label']")[
            0
        ].text.strip()
        courses_num_match = re.search(r"of (\d+) courses", courses_num_details)
        courses_num = courses_num_match.group(1)
        print(f"INFO: TOTAL COURSES: {courses_num}")
        courses_num_pages = math.ceil(int(courses_num) / 12)

        for i in range(1, courses_num_pages + 1):
            sb.uc_open(f"{courses_url}?p={i}")
            sb.wait(wait_time)
            soup = BeautifulSoup(sb.get_page_source(), "lxml")
            courses = soup.find_all("h3", attrs={"data-purpose": "course-title-url"})
            page_counter = 1
            courses_list = []

            for h3 in courses:
                course = h3.find("a")
                course_link = course.get("href")
                courses_list.append(f"https://www.udemy.com{course_link}")

            print(f"INFO: PROCESSED PAGE #{page_counter}")
            break  # DEBUG

        with open("courses_details.csv", "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["Course Title", "Course Time"])
            course_counter = 1
            courses_details = {}

            for course in courses_list:
                sb.uc_open(course)
                sb.wait(wait_time)
                sb.click(overview_selector)
                soup = BeautifulSoup(sb.get_page_source(), "lxml")
                course_time_element = soup.find(
                    "div", class_=re.compile("video-length")
                ).find(class_="ud-heading-md")
                course_time = course_time_element.text.strip()
                course_title_element = soup.find(
                    "span", class_=re.compile("course-title")
                )
                course_title = course_title_element.text.strip()
                writer.writerow([course_title, course_time])
                courses_details[course_title] = course_time
                print(f"INFO: PROCESSED COURSE #{course_counter}")
                course_counter += 1

    return courses_details


email = input("Enter email address: ")
password = input("Enter password: ")
account_name = input("Enter account first-name: ")

if checkLogin(email, password, account_name, force=False):
    print("INFO: LOGGED IN SUCCESSFULLY!")
    courses = listCourses(5)
    print("INFO: SAVED COURSE DETAILS!")
else:
    print("ERROR: LOGIN UNSUCCESSFUL!")
