import { KeyboardEvent, useEffect, useRef, useState } from 'react';
import { LogOut, UserCircle } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import type { PatientProfile } from '../api/patientApi';

interface PatientAccountMenuProps {
  profile: PatientProfile;
  onProfile: () => void;
  onSignOut: () => void;
}

export function PatientAccountMenu({ profile, onProfile, onSignOut }: PatientAccountMenuProps) {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const profileRef = useRef<HTMLButtonElement | null>(null);
  const signOutRef = useRef<HTMLButtonElement | null>(null);
  const menuId = 'patient-account-menu';
  const name = profile.fullName || `${profile.firstName} ${profile.lastName}`.trim();

  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  useEffect(() => {
    if (open) profileRef.current?.focus();
  }, [open]);

  const menuItems = [profileRef, signOutRef];

  const handleTriggerKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setOpen(true);
    }
  };

  const handleMenuKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp' && event.key !== 'Home' && event.key !== 'End') return;
    event.preventDefault();
    const activeIndex = menuItems.findIndex((item) => item.current === document.activeElement);
    let nextIndex = 0;
    if (event.key === 'End') {
      nextIndex = menuItems.length - 1;
    } else if (event.key === 'ArrowUp') {
      nextIndex = activeIndex <= 0 ? menuItems.length - 1 : activeIndex - 1;
    } else if (event.key === 'ArrowDown') {
      nextIndex = activeIndex >= menuItems.length - 1 ? 0 : activeIndex + 1;
    }
    menuItems[nextIndex]?.current?.focus();
  };

  const chooseProfile = () => {
    setOpen(false);
    onProfile();
  };

  const chooseSignOut = () => {
    setOpen(false);
    onSignOut();
  };

  return (
    <div className="patient-account-menu" ref={rootRef}>
      <button
        type="button"
        ref={triggerRef}
        className="patient-account-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={handleTriggerKeyDown}
      >
        <span className="patient-account-initials" aria-hidden>
          {initials(profile)}
        </span>
        <span>{name}</span>
      </button>
      {open && (
        <div id={menuId} className="patient-account-popover" role="menu" aria-label="Patient account" onKeyDown={handleMenuKeyDown}>
          <button type="button" role="menuitem" ref={profileRef} onClick={chooseProfile}>
            <UserCircle size={16} aria-hidden />
            <span>Profile</span>
          </button>
          <button type="button" role="menuitem" ref={signOutRef} onClick={chooseSignOut}>
            <LogOut size={16} aria-hidden />
            <span>Sign out</span>
          </button>
        </div>
      )}
    </div>
  );
}

function initials(profile: PatientProfile) {
  return `${profile.firstName.slice(0, 1)}${profile.lastName.slice(0, 1)}`.toUpperCase();
}
