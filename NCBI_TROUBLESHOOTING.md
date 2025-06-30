# NCBI E-utilities Troubleshooting Guide

## Quick Fix for "esearch not found" Errors

If you're getting errors like:
- `ERROR: NCBI esearch tool not found or not working`
- `ERROR: Please ensure NCBI E-utilities are installed and in PATH`
- `errno 2 no such file or directory: "esearch"`

Follow this troubleshooting guide step by step.

## 🔧 Quick Diagnosis and Fix

### Step 1: Run the Diagnostic Script
```bash
python3 ncbi_diagnostic.py
```

This will:
- ✅ Check your current PATH configuration
- ✅ Look for NCBI tools in all standard locations
- ✅ Test if tools are working properly
- ✅ Show shell profile configurations
- ✅ Provide specific recommendations for your system

### Step 2: Quick Installation (if tools are missing)
```bash
python3 install_ncbi_tools.py
```

This will:
- 📥 Download and install NCBI E-utilities using the official method
- 🔧 Update your shell profiles automatically
- ✅ Verify the installation works

### Step 3: Restart Terminal
After installation, **restart your terminal** or run:
```bash
# For macOS (default shell is zsh)
source ~/.zshrc

# For Linux or if using bash
source ~/.bashrc
```

### Step 4: Test the Fix
Run the diagnostic again to verify:
```bash
python3 ncbi_diagnostic.py
```

You should see: `🎉 SUCCESS: NCBI E-utilities are properly installed and working!`

## 📋 Manual Installation Methods

If the quick installation doesn't work, try these manual methods:

### Method 1: Official NCBI Installation (Recommended)
```bash
# For macOS and Linux
sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"

# Or with wget
sh -c "$(wget -q https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh -O -)"
```

### Method 2: Using Homebrew (macOS)
```bash
# Install Homebrew if not available
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install NCBI E-utilities
brew install ncbi-edirect
```

### Method 3: Using the SRA-LLM Installer
```bash
python3 install_sra_analyzer.py
```

## 🔍 Understanding the PATH Configuration

SRA-LLM looks for NCBI tools in this priority order:

1. **`/usr/local/bin`** - Homebrew Intel Mac
2. **`/opt/homebrew/bin`** - Homebrew Apple Silicon Mac
3. **`$HOME/edirect`** - Official NCBI installation (most common)
4. **`./bin`** - Local project symlinks
5. **`./ncbi_tools/edirect`** - Local project installation

## 🐛 Common Issues and Solutions

### Issue: "Tools found but not working"
**Solution:** The tools exist but may be corrupted or incomplete
```bash
# Remove existing installation
rm -rf ~/edirect

# Reinstall using official method
sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"

# Restart terminal
```

### Issue: "PATH modifications found but tools not accessible"
**Solution:** Shell profile was updated but not loaded
```bash
# Reload your shell configuration
source ~/.zshrc    # macOS (zsh)
source ~/.bashrc   # Linux (bash)

# Or restart terminal completely
```

### Issue: "Permission denied" errors
**Solution:** Installation directory permissions
```bash
# Check permissions
ls -la ~/edirect

# Fix permissions if needed
chmod +x ~/edirect/esearch ~/edirect/efetch
```

### Issue: Windows-specific problems
**Solutions:**
1. **Use WSL (Windows Subsystem for Linux):**
   ```bash
   # In WSL terminal
   sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"
   ```

2. **Use Git Bash:**
   ```bash
   # In Git Bash terminal  
   sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"
   ```

## 🔧 Advanced Troubleshooting

### Check if tools exist but not in PATH
```bash
# Search for esearch in common locations
find /usr -name "esearch" 2>/dev/null
find ~ -name "esearch" 2>/dev/null

# Check what's in your PATH
echo $PATH | tr ':' '\n' | nl
```

### Manually add tools to PATH
If you find the tools but they're not in PATH:

```bash
# Add to your shell profile (choose appropriate file)
echo 'export PATH="$HOME/edirect:$PATH"' >> ~/.zshrc    # macOS
echo 'export PATH="$HOME/edirect:$PATH"' >> ~/.bashrc   # Linux

# Reload configuration
source ~/.zshrc  # or ~/.bashrc
```

### Test tools manually
```bash
# Test if tools work
~/edirect/esearch -help
~/edirect/efetch -help

# Test a simple query
echo "cancer" | ~/edirect/esearch -db sra | ~/edirect/efetch -format runinfo | head -5
```

## 📞 Getting Help

If you're still having issues:

1. **Run the full diagnostic:**
   ```bash
   python3 ncbi_diagnostic.py > ncbi_diagnosis.txt
   ```

2. **Check the diagnostic output** in `ncbi_diagnosis.txt`

3. **Report the issue** with:
   - Your operating system and version
   - The diagnostic output
   - Any error messages you're seeing

## ✅ Verification Checklist

After following this guide, verify your installation:

- [ ] `python3 ncbi_diagnostic.py` shows SUCCESS
- [ ] `esearch -help` works without errors
- [ ] `efetch -help` works without errors  
- [ ] SRA-LLM runs without "esearch not found" errors
- [ ] You can download data successfully

---

## 📚 Additional Resources

- [NCBI E-utilities Official Documentation](https://www.ncbi.nlm.nih.gov/books/NBK179288/)
- [NCBI EDirect Installation Guide](https://www.ncbi.nlm.nih.gov/books/NBK179288/#chapter6.Getting_Started)
- [SRA-LLM Project Repository](https://github.com/schoo7/SRA_LLM)

---

*This troubleshooting guide is part of the SRA-LLM project. For the latest version, visit the GitHub repository.* 