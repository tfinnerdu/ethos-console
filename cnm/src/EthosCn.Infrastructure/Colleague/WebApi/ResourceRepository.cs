using EthosCn.Application.Common.Interfaces;
using EthosCn.Domain.Entities;

namespace EthosCn.Infrastructure.Colleague.WebApi;

/// <summary>
/// Subscribed EEDM resources from §1.3 of the CNM scope doc.
/// This is the Conductor consumer subscription list — not the full CINC publishing inventory.
/// Update when the Conductor subscription list changes.
/// </summary>
internal sealed class ResourceRepository : IResourceRepository
{
    private static readonly IReadOnlyList<EedmResource> KnownResources =
    [
        // Standard EEDM — 35 resources
        new EedmResource { Name = "academic-periods",                              DisplayName = "Academic Periods" },
        new EedmResource { Name = "academic-programs",                             DisplayName = "Academic Programs" },
        new EedmResource { Name = "addresses",                                     DisplayName = "Addresses" },
        new EedmResource { Name = "address-types",                                 DisplayName = "Address Types" },
        new EedmResource { Name = "admission-applications",                        DisplayName = "Admission Applications" },
        new EedmResource { Name = "admission-application-sources",                 DisplayName = "Admission Application Sources" },
        new EedmResource { Name = "admission-application-supporting-items",        DisplayName = "Admission Application Supporting Items" },
        new EedmResource { Name = "admission-application-supporting-item-statuses",DisplayName = "Admission Application Supporting Item Statuses" },
        new EedmResource { Name = "admission-application-supporting-item-types",   DisplayName = "Admission Application Supporting Item Types" },
        new EedmResource { Name = "admission-application-withdrawal-reasons",      DisplayName = "Admission Application Withdrawal Reasons" },
        new EedmResource { Name = "admission-decisions",                           DisplayName = "Admission Decisions" },
        new EedmResource { Name = "campus-involvements",                           DisplayName = "Campus Involvements" },
        new EedmResource { Name = "campus-organizations",                          DisplayName = "Campus Organizations" },
        new EedmResource { Name = "contribution-payroll-deductions",               DisplayName = "Contribution Payroll Deductions" },
        new EedmResource { Name = "courses",                                       DisplayName = "Courses" },
        new EedmResource { Name = "employees",                                     DisplayName = "Employees" },
        new EedmResource { Name = "external-education",                            DisplayName = "External Education" },
        new EedmResource { Name = "housing-assignments",                           DisplayName = "Housing Assignments" },
        new EedmResource { Name = "institution-jobs",                              DisplayName = "Institution Jobs" },
        new EedmResource { Name = "organizations",                                 DisplayName = "Organizations" },
        new EedmResource { Name = "payroll-deduction-arrangement-change-reasons",  DisplayName = "Payroll Deduction Arrangement Change Reasons" },
        new EedmResource { Name = "payroll-deduction-arrangements",                DisplayName = "Payroll Deduction Arrangements" },
        new EedmResource { Name = "personal-relationship-initiation-process",      DisplayName = "Personal Relationship Initiation Process", Description = "Likely RPC-style; may not emit change notifications — confirm in pre-work §0.1" },
        new EedmResource { Name = "personal-relationships",                        DisplayName = "Personal Relationships" },
        new EedmResource { Name = "person-external-education",                     DisplayName = "Person External Education" },
        new EedmResource { Name = "person-matching-requests",                      DisplayName = "Person Matching Requests" },
        new EedmResource { Name = "person-matching-requests-initiations-prospects",DisplayName = "Person Matching Requests Initiations Prospects", Description = "Likely RPC-style; may not emit change notifications — confirm in pre-work §0.1" },
        new EedmResource { Name = "persons",                                       DisplayName = "Persons" },
        new EedmResource { Name = "section-registrations",                         DisplayName = "Section Registrations" },
        new EedmResource { Name = "sections",                                      DisplayName = "Sections" },
        new EedmResource { Name = "sites",                                         DisplayName = "Sites" },
        new EedmResource { Name = "student-academic-programs",                     DisplayName = "Student Academic Programs" },
        new EedmResource { Name = "student-advisor-relationships",                 DisplayName = "Student Advisor Relationships" },
        new EedmResource { Name = "students",                                      DisplayName = "Students" },
        new EedmResource { Name = "student-transcript-grades",                     DisplayName = "Student Transcript Grades" },

        // Vendor resources (d45-*) — likely Ethos cloud-proxied, not Colleague-published; confirm in pre-work §0.1
        new EedmResource { Name = "d45-set-admit-state-v1",      DisplayName = "Set Admit State (d45)",      Description = "Vendor/partner resource — confirm origin in pre-work §0.1" },
        new EedmResource { Name = "d45-test-score-equivalency-v1",DisplayName = "Test Score Equivalency (d45)",Description = "Vendor/partner resource — confirm origin in pre-work §0.1" },
        new EedmResource { Name = "d45-test-score-matcher-v1",   DisplayName = "Test Score Matcher (d45)",   Description = "Vendor/partner resource — confirm origin in pre-work §0.1" },
        new EedmResource { Name = "d45-user-account",            DisplayName = "User Account (d45)",         Description = "Vendor/partner resource — confirm origin in pre-work §0.1" },

        // Institution-defined resources (x-dp-*) — present in CINC; display in v1 read view
        new EedmResource { Name = "x-dp-comments",           DisplayName = "Comments (Doane Custom)",           Description = "Backed by INTG-X-DP-COMMENTS" },
        new EedmResource { Name = "x-dp-restricted-comments",DisplayName = "Restricted Comments (Doane Custom)", Description = "Backed by INTG-X-DP-RESTRICTED-COMMENT" },
    ];

    public Task<IReadOnlyList<EedmResource>> GetAllAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(KnownResources);
}
