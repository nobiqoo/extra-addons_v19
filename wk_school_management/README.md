Odoo Education Management System
=================================

Odoo Education Management is designed to transform how schools handle their administrative
and academic responsibilities. 
It brings together key functionalities such as student information management, scheduling, 
enrollment processing, and teacher coordination into one seamless system.

Key Features
=============

- **Student Management**: Manage student information, enrollments, and courses.
- **Attendance Tracking**: Track student and staff attendance with ease.
- **Fee Management**: Keep track of student fees, payment history, and invoice generation.
- **Employee Management**: Manage teaching and non-teaching staff details.
- **Assignment Management**: Create, assign, and manage assignments and scores.
- **Reporting**: Generate various reports for student performance and attendances.

Usage
======

To use this module, you need to:

1. Navigate to **Education Management** > **Configuration**.
2. Firstly, configure the important settings like session details, academic year
details, grade scales, fee structures etc.
3. Proceed to **Education Management** > **Classes** > **Populate Classes**.
4. Create a new populate class as per the requirements.
5. Once these steps are completed, you can proceed further with the **Applications** and 
the **Enrollments** section.
6. Students which are created during application confirmation can be now assigned with
subjects as per their choice in enrollments which will be further used in classes.


Changelog
==========

**5.0.4 May 2026**
~~~~~~~~~~
+ Implement bi-directional sync between Student and Contact models in Odoo Education Management module.
+ Updates in common fields (name, email, phone) in Student or Contact should reflect automatically in the other record without duplication or data mismatch.
+ Allow partner creation for students even without granting portal access.
+ Enable bulk email feature in the Student model, allowing users to send emails to selected students using their linked partner emails.
~~~~~~~~~~

**5.0.3 March 2026**
~~~~~~~~~~
+ Added postponement of a scheduled class
+ Improved UI consistency across portal
+ Enhanced navigation flow for students
+ Standardized and accessible search functionality
+ Fixed mobile display issues in the Admin portal
~~~~~~~~~~

**5.0.2 March 2026**
~~~~~~~~~~
+ Added configuration to hide/show service hours in Student Portal.
+ Implemented admin ability to add documents for students and applications.
~~~~~~~~~~

**5.0.1 February 2026**
~~~~~~~~~~
+ Added Library management.
+ Added a Librarian group to manage the education library system.
~~~~~~~~~~

**5.0.0 January 2026**
~~~~~~~~~~
+ Improved portal access for students, making students the primary identity in the portal.
+ Introduced an advanced application form to control field visibility.
+ Added a unique student identifier (Student ID).
+ Introduced the ability to postpone scheduled classes and archive them.
+ Improved timezone handling to support users across different timezones.
+ Enhanced teacher access management.
~~~~~~~~~~

**4.6.2 December 2025**
~~~~~~~~~~
+ Improved fee slip payments by allowing multiple invoices for one slip.
~~~~~~~~~~

**4.6.1 December 2025**
~~~~~~~~~~
+ Improved evaluation of assignments.
+ Session required in academic year.
~~~~~~~~~~

**4.6.0 November 2025**
~~~~~~~~~~
+ Enhanced ID Card design.
+ Enhanced fee slip generation to make it compatible with mid-term enrollment.
~~~~~~~~~~

**4.5.1 September 2025**
~~~~~~~~~~
+ Enhanced mid-enrollment feature.
~~~~~~~~~~

**4.5.0 August 2025**
~~~~~~~~~~
+ Added transport management.
+ Enhanced transcript and report layouts for student and admin both.
+ Added subject code and credit value in subject.
+ Enhanced result calculation on the basis of credit values.
~~~~~~~~~~

**4.2.2 July 2025**
~~~~~~~~~~
+ Added section functionality.
+ Fee slips can now be customized by the admin, with the ability to edit amounts, dates, and other details as needed.
~~~~~~~~~~

**4.2.1 June 2025**
~~~~~~~~~~
+ Linked class attendance with student attendance.
~~~~~~~~~~

**4.2.0 June 2025**
~~~~~~~~~~
+ Added custom fee slip generation.
~~~~~~~~~~

**4.1.0 June 2025**
~~~~~~~~~~
+ Updated the teacher dashboard.
+ Added giving access to parents for student portal.
+ Parents can view the portal with full acess.
+ Students will have limited access depending upon the choice made while providing
access.
+ Added option for revoke portal access.
+ Added documents to be displayed in application form after submission of enquiry form through website.
~~~~~~~~~~

**4.0.0 May 2025**
~~~~~~~~~~
+ Implemented barcode scanning for attendance tracking.
+ Displayed scholarship information on the student portal and in enrollments.
+ Added support for ID card printing in both horizontal and vertical layouts, based on the selected design preference.
+ Removed individual QR scanning,now qr scanning can also be done from barcode scanner.
~~~~~~~~~~

**3.1.0 March 2025**
~~~~~~~~~~

+ Added a manual scholarship feature for providing scholarships to students.
+ An invoice(vendor bill) generation on successful payment of scholarships.
~~~~~~~~~~


**3.0.0 March 2025**
~~~~~~~~~~

+ Enhanced the student attendance process by integrating QR code scanning, allowing for quicker and more accurate attendance marking directly from the kiosk.
+ Added 'View Status' button in application email notifications for quick access.
+ Introduced a 'Get Directions' button on admission enquriy form for easy redirection to the address.
~~~~~~~~~~


**2.0.0 February 2025**
~~~~~~~~~~

+ Introduced an analytical dashboard for admins and teachers to track applications, enrollments, assignments, classes, and attendance.
+ Introduced a feature to check application status by number.
+ Automated email notifications when application status changes (confirmed, enrolled, cancelled).
+ Ensured a PDF with application details is attached in the confirmation email.
+ Added multi-branch compatibility.
+ Redesigned the admission enquiry form with captcha and a map.
~~~~~~~~~~


**1.1.0 January 2025**
~~~~~~~~~~

+ Designed the all new class timetable dashboard for teachers and admin.
+ Attached the invoice pdf in successful fee payment mail.
+ Updated the doc.
~~~~~~~~~~


**1.0.0 January 2025(Initial Release)**
~~~~~~~~~~

+ Launched the module with all in one dashboard with different access rights for admin, officer and staff.
+ Smart Session, Academic Year and Terms Management.
+ Smart Enrollment and Applications Management .
+ Efficient Class and Student Management.
+ Attendance Tracking Options.
+ Class Scheduling.
+ Transcripts and Gradesheet Generation.
+ Assignment Tracking Tools.
+ Interactive Student Portal.
+ Community Service and Discipline Tracking.
+ Advance Fee Slip Generation and Management.
+ Customizable Grading System.
+ Automated ID Card Generation.
~~~~~~~~~~

Credits
=======

Authors
~~~~~~~

* Webkul Software Pvt. Ltd.
